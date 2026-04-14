import streamlit as st
import altair as alt
import pandas as pd
from app_pages.styling import inject_gov_uk_css, short_period
from app_pages.queries import load_delay_causes

inject_gov_uk_css()

st.title("Delay causes")
st.caption("Breakdown of delay minutes by responsible party and cause category")

delays = load_delay_causes()
operators = sorted(delays["TRAIN_OPERATING_COMPANY"].unique())
years = sorted(delays["FINANCIAL_YEAR"].dropna().unique(), reverse=True)

with st.sidebar:
    view_mode = st.radio("View", ["All operators (aggregated)", "Single operator"], index=0)
    if view_mode == "Single operator":
        selected_op = st.selectbox("Operator", operators, index=operators.index("Avanti West Coast") if "Avanti West Coast" in operators else 0)
    selected_year = st.selectbox("Financial year", years, index=0)

if view_mode == "All operators (aggregated)":
    df = delays[delays["FINANCIAL_YEAR"] == selected_year].copy()
else:
    df = delays[(delays["FINANCIAL_YEAR"] == selected_year) & (delays["TRAIN_OPERATING_COMPANY"] == selected_op)].copy()

totals = df[["TOTAL_NR_CAUSED_DELAY_MINS", "TOTAL_TOC_SELF_DELAY_MINS", "TOTAL_TOC_OTHER_DELAY_MINS"]].sum()
grand_total = totals.sum()

with st.container(horizontal=True):
    st.metric("Total delay mins", f"{grand_total:,.0f}", border=True)
    nr_pct = (totals["TOTAL_NR_CAUSED_DELAY_MINS"] / grand_total * 100) if grand_total > 0 else 0
    toc_pct = (totals["TOTAL_TOC_SELF_DELAY_MINS"] / grand_total * 100) if grand_total > 0 else 0
    st.metric("Network Rail caused", f"{nr_pct:.0f}%", border=True)
    st.metric("TOC self-caused", f"{toc_pct:.0f}%", border=True)
    st.metric("Weather delay mins", f"{df['WEATHER_DELAY_MINS'].sum():,.0f}", border=True)

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.subheader("Delay attribution split")
        pie_data = pd.DataFrame({
            "Category": ["Network Rail", "TOC (self)", "TOC (other operators)"],
            "Minutes": [
                totals["TOTAL_NR_CAUSED_DELAY_MINS"],
                totals["TOTAL_TOC_SELF_DELAY_MINS"],
                totals["TOTAL_TOC_OTHER_DELAY_MINS"],
            ],
        })
        pie = (
            alt.Chart(pie_data)
            .mark_arc(innerRadius=50)
            .encode(
                theta=alt.Theta("Minutes:Q"),
                color=alt.Color(
                    "Category:N",
                    scale=alt.Scale(
                        domain=["Network Rail", "TOC (self)", "TOC (other operators)"],
                        range=["#1d70b8", "#0f7a52", "#f47738"],
                    ),
                ),
                tooltip=["Category", "Minutes"],
            )
            .properties(height=350)
        )
        st.altair_chart(pie)

with col2:
    with st.container(border=True):
        st.subheader("Detailed cause breakdown")
        cause_data = pd.DataFrame({
            "Cause": ["Weather", "Track", "Fleet", "Traincrew", "Other NR", "Other TOC"],
            "Minutes": [
                df["WEATHER_DELAY_MINS"].sum(),
                df["TRACK_DELAY_MINS"].sum(),
                df["TOTAL_FLEET_DELAY_MINS"].sum(),
                df["TOTAL_TRAINCREW_DELAY_MINS"].sum(),
                totals["TOTAL_NR_CAUSED_DELAY_MINS"] - df["WEATHER_DELAY_MINS"].sum() - df["TRACK_DELAY_MINS"].sum(),
                totals["TOTAL_TOC_SELF_DELAY_MINS"] + totals["TOTAL_TOC_OTHER_DELAY_MINS"] - df["TOTAL_FLEET_DELAY_MINS"].sum() - df["TOTAL_TRAINCREW_DELAY_MINS"].sum(),
            ],
        })
        bar = (
            alt.Chart(cause_data)
            .mark_bar()
            .encode(
                x=alt.X("Minutes:Q", title="Delay minutes"),
                y=alt.Y("Cause:N", title="", sort="-x"),
                color=alt.Color(
                    "Cause:N",
                    scale=alt.Scale(
                        domain=["Weather", "Track", "Fleet", "Traincrew", "Other NR", "Other TOC"],
                        range=["#158187", "#1d70b8", "#0f7a52", "#f47738", "#54319f", "#ca357c"],
                    ),
                    legend=None,
                ),
                tooltip=["Cause", "Minutes"],
            )
            .properties(height=350)
        )
        st.altair_chart(bar)

with st.container(border=True):
    st.subheader("Delay trend by period")
    df["PERIOD_NUMBER"] = df["PERIOD_NUMBER"].astype(int)
    period_agg = df.groupby(["TIME_PERIOD", "PERIOD_NUMBER"]).agg(
        NR=("TOTAL_NR_CAUSED_DELAY_MINS", "sum"),
        TOC=("TOTAL_TOC_SELF_DELAY_MINS", "sum"),
    ).reset_index().sort_values("PERIOD_NUMBER")
    period_agg["PERIOD_LABEL"] = period_agg["TIME_PERIOD"].apply(short_period)

    melted = period_agg.melt(
        id_vars=["TIME_PERIOD", "PERIOD_NUMBER", "PERIOD_LABEL"],
        value_vars=["NR", "TOC"],
        var_name="Attribution",
        value_name="Minutes",
    )

    area = (
        alt.Chart(melted)
        .mark_area(opacity=0.7)
        .encode(
            x=alt.X("PERIOD_LABEL:N", title="Period", sort=None),
            y=alt.Y("Minutes:Q", title="Delay minutes", stack=True),
            color=alt.Color(
                "Attribution:N",
                scale=alt.Scale(domain=["NR", "TOC"], range=["#1d70b8", "#0f7a52"]),
            ),
            tooltip=["TIME_PERIOD", "Attribution", "Minutes"],
        )
        .properties(height=350)
    )
    st.altair_chart(area)
