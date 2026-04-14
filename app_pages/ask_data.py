import streamlit as st
import pandas as pd
from app_pages.styling import inject_gov_uk_css
from app_pages.queries import get_conn, _query

inject_gov_uk_css()

st.title("Ask the data")
st.caption("Powered by Snowflake Cortex — ask natural language questions about GB rail performance")

SYSTEM_PROMPT = """You are a GB rail performance analyst. You have access to these Snowflake tables:

1. DFT_PPM.PROCESSED.PPM_BY_OPERATOR — columns: TIME_PERIOD, FINANCIAL_YEAR, PERIOD_NUMBER, OPERATOR, CATEGORY (Franchised/Open Access/Sector/National), PPM_PERCENTAGE
2. DFT_PPM.PROCESSED.CANCELLATIONS_BY_OPERATOR — columns: TIME_PERIOD, FINANCIAL_YEAR, PERIOD_NUMBER, OPERATOR, TRAINS_PLANNED, TRAINS_PART_CANCELLED, TRAINS_FULL_CANCELLED, CANCELLATION_NUMBER, CANCELLATIONS_PERCENTAGE
3. DFT_PPM.PROCESSED.DELAY_CAUSES_SUMMARY — columns: TIME_PERIOD, FINANCIAL_YEAR, PERIOD_NUMBER, TRAIN_OPERATING_COMPANY, TOTAL_NR_CAUSED_DELAY_MINS, TOTAL_TOC_SELF_DELAY_MINS, TOTAL_TOC_OTHER_DELAY_MINS, WEATHER_DELAY_MINS, TRACK_DELAY_MINS, TOTAL_FLEET_DELAY_MINS, TOTAL_TRAINCREW_DELAY_MINS
4. DFT_PPM.ANALYTICS.INTERNATIONAL_PPM_LEAGUE — columns: RAILWAY, COUNTRY, PPM_PERCENT, METRIC, THRESHOLD_MINUTES, PERFORMANCE_CATEGORY, GAP_TO_GB_PPM, LEAGUE_POSITION
5. DFT_PPM.RAW.RAILWAY_STATIONS — columns: STATION_NAME, LATITUDE, LONGITUDE, REGION, COUNTY_UNITARY, COUNTRY, POSTCODE_DISTRICT (3,323 stations)

Key facts:
- PPM = Public Performance Measure. On time = within 5 min (regional/LSE) or 10 min (long distance)
- GB composite PPM is 80.4%, ranking 12th of 14 globally
- 24 train operating companies (TOCs), plus aggregates like "National Great Britain"
- Data covers FY19/20 to FY25/26, 13 periods per financial year
- Financial years run April to March

When the user asks a question, generate a SQL query to answer it, then explain the results clearly and concisely. Return the SQL in a ```sql code block so it can be executed.
If the question doesn't need SQL (e.g. general knowledge), answer directly.
Always be concise and use bullet points where helpful."""

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

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
        with st.spinner("Thinking..."):
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

            sql_blocks = []
            if "```sql" in response:
                parts = response.split("```sql")
                for part in parts[1:]:
                    if "```" in part:
                        sql_blocks.append(part.split("```")[0].strip())

            st.markdown(response)

            for sql in sql_blocks:
                with st.expander("Run this query", expanded=False):
                    try:
                        df = _query(sql)
                        st.dataframe(df, hide_index=True)
                    except Exception as e:
                        st.error(f"Query error: {e}")

    st.session_state.messages.append({"role": "assistant", "content": response})

with st.sidebar:
    if st.button("Clear conversation", key="clear_chat"):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.caption("Powered by Snowflake Cortex (mistral-large2)")
    st.caption("Queries run against DFT_PPM database")
