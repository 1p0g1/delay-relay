import streamlit as st
import altair as alt
from app_pages.styling import inject_gov_uk_css, short_period, short_fy
from app_pages.queries import load_ppm_trend

inject_gov_uk_css()

st.title("Operator drill-down")
st.caption("Compare PPM performance across train operating companies")

trend = load_ppm_trend()

operators = sorted(trend[trend["CATEGORY"].isin(["Franchised", "Open Access"])]["OPERATOR"].unique())
years = sorted(trend["FINANCIAL_YEAR"].dropna().unique(), reverse=True)

with st.sidebar:
    selected_operators = st.multiselect(
        "Select operators",
        operators,
        default=[o for o in [
            "Avanti West Coast", "ScotRail", "Greater Anglia", "Northern Trains",
            "South Western Railway", "CrossCountry", "Govia Thameslink Railway",
            "TransPennine Express",
        ] if o in operators],
    )
    selected_years = st.multiselect(
        "Financial year",
        years,
        default=years[:2],
    )

if not selected_operators:
    st.info("Select at least one operator from the sidebar.", icon=":material/info:")
    st.stop()

filtered = trend[
    (trend["OPERATOR"].isin(selected_operators))
    & (trend["FINANCIAL_YEAR"].isin(selected_years))
].copy()
filtered["PERIOD_NUMBER"] = filtered["PERIOD_NUMBER"].astype(int)
filtered = filtered.sort_values(["FINANCIAL_YEAR", "PERIOD_NUMBER"])
filtered["PERIOD_LABEL"] = filtered["TIME_PERIOD"].apply(short_period)
filtered["FY_SHORT"] = filtered["FINANCIAL_YEAR"].apply(short_fy)

with st.container(border=True):
    st.subheader("PPM trend by operator")
    chart = (
        alt.Chart(filtered)
        .mark_line(point=True)
        .encode(
            x=alt.X("PERIOD_LABEL:N", title="Period", sort=None),
            y=alt.Y("PPM_PERCENTAGE:Q", title="PPM %", scale=alt.Scale(domain=[50, 100])),
            color=alt.Color("OPERATOR:N", title="Operator"),
            strokeDash=alt.StrokeDash("FY_SHORT:N", title="Year"),
            tooltip=["TIME_PERIOD", "OPERATOR", "PPM_PERCENTAGE", "FINANCIAL_YEAR"],
        )
        .properties(height=450)
    )
    st.altair_chart(chart)

with st.container(border=True):
    st.subheader("Latest period comparison")
    latest_period = filtered["TIME_PERIOD"].max()
    latest = filtered[filtered["TIME_PERIOD"] == latest_period]

    latest["BAR_COLOR"] = latest["PPM_PERCENTAGE"].apply(
        lambda v: "#0f7a52" if v >= 92.5 else ("#f47738" if v >= 85 else "#ca3535")
    )

    bar = (
        alt.Chart(latest)
        .mark_bar()
        .encode(
            x=alt.X("PPM_PERCENTAGE:Q", title="PPM %", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("OPERATOR:N", title="", sort="-x"),
            color=alt.Color("BAR_COLOR:N", scale=None),
            tooltip=["OPERATOR", "PPM_PERCENTAGE"],
        )
        .properties(height=max(len(selected_operators) * 40, 200))
    )

    rule = alt.Chart().mark_rule(color="#1d70b8", strokeDash=[4, 4]).encode(
        x=alt.datum(92.5)
    )
    st.altair_chart(bar + rule)
    st.caption("Dashed line = 92.5% green threshold")

with st.container(border=True):
    st.subheader("Period-over-period data")
    st.dataframe(
        filtered[["TIME_PERIOD", "OPERATOR", "PPM_PERCENTAGE", "FINANCIAL_YEAR"]].rename(
            columns={
                "TIME_PERIOD": "Period",
                "OPERATOR": "Operator",
                "PPM_PERCENTAGE": "PPM %",
                "FINANCIAL_YEAR": "Year",
            }
        ),
        column_config={
            "PPM %": st.column_config.NumberColumn(format="%.1f"),
        },
        hide_index=True,
    )
