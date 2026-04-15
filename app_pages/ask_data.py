import streamlit as st
import pandas as pd
import time
from app_pages.styling import inject_gov_uk_css
from app_pages.queries import get_conn, _query

inject_gov_uk_css()

st.title("Ask the data")
st.caption("Powered by Snowflake Cortex — ask natural language questions about GB rail performance")

SYSTEM_PROMPT = """You are a GB rail performance analyst. You have access to these Snowflake tables:

1. DFT_PPM.PROCESSED.PPM_BY_OPERATOR — columns: TIME_PERIOD, FINANCIAL_YEAR, PERIOD_NUMBER, OPERATOR, CATEGORY (Franchised/Open Access/Sector/National), PPM_PERCENTAGE
2. DFT_PPM.PROCESSED.CANCELLATIONS_BY_OPERATOR — columns: TIME_PERIOD, FINANCIAL_YEAR, PERIOD_NUMBER, OPERATOR, TRAINS_PLANNED, TRAINS_PART_CANCELLED, TRAINS_FULL_CANCELLED, CANCELLATION_NUMBER, CANCELLATIONS_PERCENTAGE
3. DFT_PPM.PROCESSED.DELAY_CAUSES_SUMMARY — columns: TIME_PERIOD, FINANCIAL_YEAR, PERIOD_NUMBER, TRAIN_OPERATING_COMPANY, TOTAL_NR_CAUSED_DELAY_MINS, TOTAL_TOC_SELF_DELAY_MINS, TOTAL_TOC_OTHER_DELAY_MINS, WEATHER_DELAY_MINS, TRACK_DELAY_MINS, TOTAL_FLEET_DELAY_MINS, TOTAL_TRAINCREW_DELAY_MINS
4. DFT_PPM.ANALYTICS.INTERNATIONAL_PPM_LEAGUE — columns: RAILWAY, COUNTRY, PPM_PERCENT, METRIC, THRESHOLD_MINUTES, PERFORMANCE_CATEGORY, OPERATOR_COVERAGE, DATA_SOURCE, GAP_TO_GB_PPM, LEAGUE_POSITION
5. DFT_PPM.RAW.RAILWAY_STATIONS — columns: STATION_NAME, LATITUDE, LONGITUDE, REGION, COUNTY_UNITARY, COUNTRY, POSTCODE_DISTRICT (3,323 stations)

Key facts:
- PPM = Public Performance Measure. On time = within 5 min (regional/LSE) or 10 min (long distance)
- GB composite PPM is 80.4%, ranking 12th of 14 globally
- 24 train operating companies (TOCs), plus aggregates like "National Great Britain"
- Data covers FY19/20 to FY25/26, 13 periods per financial year
- Financial years run April to March

When the user asks a question, generate a SQL query to answer it.
Return the SQL in a ```sql code block so it can be executed.
If the question doesn't need SQL (e.g. general knowledge), answer directly.
Keep your initial response brief — the SQL results will be analysed separately."""

SUMMARY_PROMPT = """You are a GB rail performance analyst. The user asked: "{question}"

The SQL query returned the following data (first 50 rows shown):
{data}

Provide a clear, concise natural language answer to the user's question based on this data.
Use bullet points where helpful. Highlight key numbers. Be direct and insightful.
Do NOT include any SQL in your response. Do NOT say "based on the data" — just answer naturally."""

TRAIN_FRAMES = [
    "🚂       ",
    " 🚂      ",
    "  🚂     ",
    "   🚂    ",
    "    🚂   ",
    "     🚂  ",
    "      🚂 ",
    "       🚂",
    "      🚂 ",
    "     🚂  ",
    "    🚂   ",
    "   🚂    ",
    "  🚂     ",
    " 🚂      ",
]

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "dataframe" in msg:
            with st.expander("Query results", expanded=False):
                st.dataframe(msg["dataframe"], hide_index=True)

EXAMPLES = [
    "Which operator has the best PPM in the latest period?",
    "How many stations are in Scotland?",
    "What's the total delay minutes caused by weather across all operators?",
    "Compare Avanti West Coast vs ScotRail cancellation rates",
    "Which countries beat GB in on-time performance?",
]

if not st.session_state.messages:
    st.markdown("**Try asking:**")
    cols = st.columns(len(EXAMPLES))
    for i, ex in enumerate(EXAMPLES):
        if cols[i].button(ex, key=f"ex_{i}", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": ex})
            st.rerun()

if prompt := st.chat_input("Ask about GB rail performance..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    user_q = st.session_state.messages[-1]["content"]
    with st.chat_message("assistant"):
        train_placeholder = st.empty()
        frame_idx = 0

        def _advance_train():
            nonlocal frame_idx
            train_placeholder.markdown(
                f"<div style='font-size:1.6rem; letter-spacing:2px; font-family:monospace;'>"
                f"{TRAIN_FRAMES[frame_idx % len(TRAIN_FRAMES)]}"
                f"<span style='color:#b1b4b6; font-size:0.85rem;'> Querying the network...</span></div>",
                unsafe_allow_html=True,
            )
            frame_idx += 1

        _advance_train()

        conversation = "\n".join(
            [f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages[-6:]]
        )
        full_prompt = f"{SYSTEM_PROMPT}\n\nConversation:\n{conversation}\n\nASSISTANT:"

        try:
            result = _query(
                "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s) AS RESPONSE",
                params=["mistral-large2", full_prompt],
            )
            response = result["RESPONSE"].values[0] if len(result) > 0 else "No response generated."
        except Exception as e:
            response = f"Error calling Cortex: {e}"

        _advance_train()

        sql_blocks = []
        if "```sql" in response:
            parts = response.split("```sql")
            for part in parts[1:]:
                if "```" in part:
                    sql_blocks.append(part.split("```")[0].strip())

        query_results = []
        for sql in sql_blocks:
            _advance_train()
            try:
                df = _query(sql)
                query_results.append({"sql": sql, "df": df, "error": None})
            except Exception as e:
                query_results.append({"sql": sql, "df": None, "error": str(e)})

        summary = None
        if query_results and any(r["df"] is not None and len(r["df"]) > 0 for r in query_results):
            _advance_train()
            all_data = []
            for r in query_results:
                if r["df"] is not None:
                    all_data.append(r["df"].head(50).to_string(index=False))
            data_str = "\n---\n".join(all_data)

            summary_input = SUMMARY_PROMPT.format(question=user_q, data=data_str)
            try:
                summary_result = _query(
                    "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s) AS RESPONSE",
                    params=["mistral-large2", summary_input],
                )
                summary = summary_result["RESPONSE"].values[0] if len(summary_result) > 0 else None
            except Exception:
                summary = None

        train_placeholder.empty()

        if summary:
            st.markdown(summary)
        else:
            st.markdown(response)

        first_df = None
        for r in query_results:
            if r["df"] is not None:
                if first_df is None:
                    first_df = r["df"]
                with st.expander("Query results", expanded=False):
                    st.dataframe(r["df"], hide_index=True)
            elif r["error"]:
                st.error(f"Query error: {r['error']}")

        display_content = summary if summary else response
        msg_entry = {"role": "assistant", "content": display_content}
        if first_df is not None:
            msg_entry["dataframe"] = first_df
        st.session_state.messages.append(msg_entry)

with st.sidebar:
    if st.button("Clear conversation", key="clear_chat"):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.caption("Powered by Snowflake Cortex (mistral-large2)")
    st.caption("Queries run against DFT_PPM database")
