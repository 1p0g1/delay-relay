import streamlit as st
import altair as alt
from app_pages.styling import inject_gov_uk_css, short_period
from app_pages.queries import load_cancellations

inject_gov_uk_css()

st.title("Cancellations")
st.caption("Trains planned, part-cancelled and fully cancelled by operator")

canc = load_cancellations()

AGGREGATES = {"Great Britain", "England and Wales", "Scotland"}
tocs = canc[~canc["OPERATOR"].isin(AGGREGATES)].copy()
operators = sorted(tocs["OPERATOR"].unique())
years = sorted(tocs["FINANCIAL_YEAR"].dropna().unique(), reverse=True)

with st.sidebar:
    selected_year = st.selectbox("Financial year", years, index=0, key="canc_year")
    selected_ops = st.multiselect(
        "Operators",
        operators,
        default=[o for o in [
            "Avanti West Coast", "Northern Trains", "ScotRail",
            "Greater Anglia", "South Western Railway", "CrossCountry",
            "Govia Thameslink Railway", "TransPennine Express",
        ] if o in operators],
        key="canc_ops",
    )

if not selected_ops:
    st.info("Select at least one operator from the sidebar.", icon=":material/info:")
    st.stop()

df = tocs[(tocs["FINANCIAL_YEAR"] == selected_year) & (tocs["OPERATOR"].isin(selected_ops))].copy()

gb = canc[(canc["FINANCIAL_YEAR"] == selected_year) & (canc["OPERATOR"] == "Great Britain")]
if len(gb) > 0:
    total_planned = gb["TRAINS_PLANNED"].sum()
    total_cancelled = gb["CANCELLATION_NUMBER"].sum()
    avg_pct = gb["CANCELLATIONS_PERCENTAGE"].mean()
    with st.container(horizontal=True):
        st.metric("Trains planned (GB total)", f"{total_planned:,.0f}", border=True)
        st.metric("Cancellations (GB total)", f"{total_cancelled:,.0f}", border=True)
        st.metric("GB avg cancellation rate", f"{avg_pct:.1f}%", border=True)

with st.container(border=True):
    st.subheader("Cancellation rate trend")
    df["PERIOD_NUMBER"] = df["PERIOD_NUMBER"].astype(int)
    df = df.sort_values(["FINANCIAL_YEAR", "PERIOD_NUMBER"])
    df["PERIOD_LABEL"] = df["TIME_PERIOD"].apply(short_period)

    chart = (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X("PERIOD_LABEL:N", title="Period", sort=None),
            y=alt.Y("CANCELLATIONS_PERCENTAGE:Q", title="Cancellation %"),
            color=alt.Color("OPERATOR:N", title="Operator"),
            tooltip=["TIME_PERIOD", "OPERATOR", "CANCELLATIONS_PERCENTAGE", "TRAINS_PLANNED"],
        )
        .properties(height=400)
    )
    st.altair_chart(chart)

with st.container(border=True):
    st.subheader("Trains planned vs cancelled")
    latest_period = df["TIME_PERIOD"].max()
    latest = df[df["TIME_PERIOD"] == latest_period].copy()

    bar = (
        alt.Chart(latest)
        .mark_bar()
        .encode(
            x=alt.X("CANCELLATION_NUMBER:Q", title="Cancellation score"),
            y=alt.Y("OPERATOR:N", title="", sort="-x"),
            color=alt.value("#ca3535"),
            tooltip=["OPERATOR", "TRAINS_PLANNED", "TRAINS_PART_CANCELLED", "TRAINS_FULL_CANCELLED", "CANCELLATION_NUMBER"],
        )
        .properties(height=max(len(selected_ops) * 40, 200))
    )
    st.altair_chart(bar)
    st.caption(f"Period: {latest_period}")

with st.container(border=True):
    st.subheader("Detailed data")
    st.dataframe(
        df[["TIME_PERIOD", "OPERATOR", "TRAINS_PLANNED", "TRAINS_PART_CANCELLED", "TRAINS_FULL_CANCELLED", "CANCELLATIONS_PERCENTAGE"]].rename(
            columns={
                "TIME_PERIOD": "Period",
                "OPERATOR": "Operator",
                "TRAINS_PLANNED": "Planned",
                "TRAINS_PART_CANCELLED": "Part cancelled",
                "TRAINS_FULL_CANCELLED": "Full cancelled",
                "CANCELLATIONS_PERCENTAGE": "Cancel %",
            }
        ),
        column_config={
            "Planned": st.column_config.NumberColumn(format="%,.0f"),
            "Part cancelled": st.column_config.NumberColumn(format="%,.0f"),
            "Full cancelled": st.column_config.NumberColumn(format="%,.0f"),
            "Cancel %": st.column_config.NumberColumn(format="%.2f"),
        },
        hide_index=True,
    )
