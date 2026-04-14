import streamlit as st
import altair as alt
from app_pages.styling import inject_gov_uk_css, rag_badge, short_period, short_fy
from app_pages.queries import load_ppm_summary, load_ppm_trend

inject_gov_uk_css()

st.title("PPM overview")
st.caption("Public Performance Measure — GB Rail punctuality at a glance")

summary = load_ppm_summary()

gb_row = summary[summary["OPERATOR"] == "National Great Britain"]
lse_row = summary[summary["CATEGORY"] == "Sector"]
best_row = summary[summary["CATEGORY"].isin(["Franchised", "Open Access"])].head(1)
worst_row = summary[summary["CATEGORY"].isin(["Franchised", "Open Access"])].tail(1)

gb_ppm = gb_row["LATEST_PPM"].values[0] if len(gb_row) > 0 else 0
gb_change = gb_row["PPM_CHANGE"].values[0] if len(gb_row) > 0 else 0
gb_period = gb_row["LATEST_PERIOD"].values[0] if len(gb_row) > 0 else "N/A"

with st.container(horizontal=True):
    st.metric(
        "National PPM",
        f"{gb_ppm:.1f}%",
        f"{gb_change:+.1f}pp",
        border=True,
    )
    if len(best_row) > 0:
        st.metric(
            f"Best: {best_row['OPERATOR'].values[0]}",
            f"{best_row['LATEST_PPM'].values[0]:.1f}%",
            f"{best_row['PPM_CHANGE'].values[0]:+.1f}pp",
            border=True,
        )
    if len(worst_row) > 0:
        st.metric(
            f"Worst: {worst_row['OPERATOR'].values[0]}",
            f"{worst_row['LATEST_PPM'].values[0]:.1f}%",
            f"{worst_row['PPM_CHANGE'].values[0]:+.1f}pp",
            border=True,
        )
    green_count = len(summary[summary["RAG_STATUS"] == "GREEN"])
    amber_count = len(summary[summary["RAG_STATUS"] == "AMBER"])
    red_count = len(summary[summary["RAG_STATUS"] == "RED"])
    st.metric("RAG split", f"{green_count}G / {amber_count}A / {red_count}R", border=True)

st.caption(f"Latest period: {gb_period}")

col_chart, col_table = st.columns([3, 2])

with col_chart:
    with st.container(border=True):
        st.subheader("National PPM trend")
        trend = load_ppm_trend()
        national = trend[trend["OPERATOR"] == "National Great Britain"].copy()
        national["PERIOD_NUMBER"] = national["PERIOD_NUMBER"].astype(int)
        national = national.sort_values(["FINANCIAL_YEAR", "PERIOD_NUMBER"])
        national["PERIOD_LABEL"] = national["TIME_PERIOD"].apply(short_period)
        national["FY_SHORT"] = national["FINANCIAL_YEAR"].apply(short_fy)

        chart = (
            alt.Chart(national)
            .mark_line(point=True)
            .encode(
                x=alt.X("PERIOD_LABEL:N", title="Period", sort=None),
                y=alt.Y("PPM_PERCENTAGE:Q", title="PPM %", scale=alt.Scale(domain=[70, 100])),
                color=alt.Color("FY_SHORT:N", title="Financial year"),
                tooltip=["TIME_PERIOD", "PPM_PERCENTAGE", "FINANCIAL_YEAR"],
            )
            .properties(height=400)
        )
        st.altair_chart(chart)

with col_table:
    with st.container(border=True):
        st.subheader("Operator RAG status")
        operators_only = summary[summary["CATEGORY"].isin(["Franchised", "Open Access"])].copy()
        operators_only["Status"] = operators_only["RAG_STATUS"].map(
            {"GREEN": "🟢", "AMBER": "🟠", "RED": "🔴"}
        )
        st.dataframe(
            operators_only[["OPERATOR", "LATEST_PPM", "PPM_CHANGE", "Status"]].rename(
                columns={
                    "OPERATOR": "Operator",
                    "LATEST_PPM": "PPM %",
                    "PPM_CHANGE": "Change (pp)",
                }
            ),
            column_config={
                "PPM %": st.column_config.NumberColumn(format="%.1f"),
                "Change (pp)": st.column_config.NumberColumn(format="%+.1f"),
            },
            hide_index=True,
            height=420,
        )

with st.container(border=True):
    st.subheader("Sector comparison")
    sectors = trend[trend["CATEGORY"] == "Sector"].copy()
    sectors["PERIOD_NUMBER"] = sectors["PERIOD_NUMBER"].astype(int)
    sectors = sectors.sort_values(["FINANCIAL_YEAR", "PERIOD_NUMBER"])
    sectors["PERIOD_LABEL"] = sectors["TIME_PERIOD"].apply(short_period)
    sectors["FY_SHORT"] = sectors["FINANCIAL_YEAR"].apply(short_fy)

    sector_chart = (
        alt.Chart(sectors)
        .mark_line(point=True)
        .encode(
            x=alt.X("PERIOD_LABEL:N", title="Period", sort=None),
            y=alt.Y("PPM_PERCENTAGE:Q", title="PPM %", scale=alt.Scale(domain=[70, 100])),
            color=alt.Color("OPERATOR:N", title="Sector"),
            tooltip=["TIME_PERIOD", "OPERATOR", "PPM_PERCENTAGE"],
        )
        .properties(height=350)
    )
    st.altair_chart(sector_chart)
