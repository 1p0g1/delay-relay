import json
import streamlit as st
import altair as alt
import pandas as pd
from app_pages.styling import inject_gov_uk_css
from app_pages.queries import load_dq_results, load_dq_inventory


def _extract_columns(ref_args) -> str:
    if not ref_args or ref_args == "[]":
        return "(table-level)"
    try:
        if isinstance(ref_args, str):
            args = json.loads(ref_args)
        else:
            args = ref_args
        cols = [a.get("name", "") for a in args if a.get("domain") == "COLUMN"]
        return ", ".join(cols) if cols else "(table-level)"
    except Exception:
        return str(ref_args)


inject_gov_uk_css()

st.title("Data quality monitoring")
st.caption("Snowflake Data Metric Functions (DMFs) — automated quality checks across all ORR tables")

inventory = load_dq_inventory()
results = load_dq_results()

total_dmfs = len(inventory)
tables_monitored = inventory["TBL_NAME"].nunique() if len(inventory) > 0 else 0
all_started = (inventory["SCHEDULE_STATUS"] == "STARTED").all() if len(inventory) > 0 else False

with st.container(horizontal=True):
    st.metric("DMFs attached", total_dmfs, border=True)
    st.metric("Tables monitored", tables_monitored, border=True)
    st.metric("Schedule", "Trigger on changes", border=True)

    if len(results) > 0:
        latest = results.drop_duplicates(subset=["TBL_NAME", "METRIC_NAME", "ARGUMENT_NAMES"], keep="first")
        passing = latest[latest["VALUE"].astype(float) == 0]
        health_pct = round(len(passing) / len(latest) * 100, 1) if len(latest) > 0 else 0
        st.metric("Health score", f"{health_pct}%", border=True)
    else:
        st.metric("Health score", "Awaiting first run", border=True)

st.divider()

with st.container(border=True):
    st.subheader("DMF inventory")
    st.caption("All Data Metric Functions attached to DFT_PPM tables")

    if len(inventory) > 0:
        inv_display = inventory.copy()
        inv_display["DMF_SOURCE"] = inv_display.apply(
            lambda r: "Custom" if r["METRIC_DATABASE_NAME"] == "DFT_PPM" else "Built-in",
            axis=1,
        )
        inv_display["COLUMN"] = inv_display["REF_ARGUMENTS"].apply(
            lambda x: _extract_columns(x)
        )
        st.dataframe(
            inv_display[["TBL_SCHEMA", "TBL_NAME", "METRIC_NAME", "DMF_SOURCE", "COLUMN", "SCHEDULE", "SCHEDULE_STATUS"]],
            column_config={
                "TBL_SCHEMA": "Schema",
                "TBL_NAME": "Table",
                "METRIC_NAME": "DMF",
                "DMF_SOURCE": "Type",
                "COLUMN": "Column(s)",
                "SCHEDULE": "Schedule",
                "SCHEDULE_STATUS": "Status",
            },
            hide_index=True,
            height=min(len(inv_display) * 40 + 40, 600),
        )
    else:
        st.info("No DMFs found. Attach DMFs to tables to begin monitoring.", icon=":material/info:")

if len(results) > 0:
    with st.container(border=True):
        st.subheader("Latest DMF results")
        st.caption("Most recent measurement per metric — 0 = passing (no issues found)")

        latest = results.drop_duplicates(subset=["TBL_NAME", "METRIC_NAME", "ARGUMENT_NAMES"], keep="first").copy()
        latest["VALUE"] = latest["VALUE"].astype(float).astype(int)
        latest["STATUS"] = latest["VALUE"].apply(lambda v: "PASS" if v == 0 else ("INFO" if v > 0 else "PASS"))
        latest["STATUS_ICON"] = latest.apply(
            lambda r: "🟢" if r["METRIC_NAME"] == "ROW_COUNT" or r["VALUE"] == 0
            else ("🔵" if r["METRIC_NAME"] == "ROW_COUNT" else "🔴"),
            axis=1,
        )
        latest["COLUMN"] = latest["ARGUMENT_NAMES"].apply(lambda x: _extract_columns(x))

        for name in ["ROW_COUNT", "FRESHNESS"]:
            mask = latest["METRIC_NAME"] == name
            latest.loc[mask, "STATUS_ICON"] = "🔵"

        st.dataframe(
            latest[["TBL_NAME", "METRIC_NAME", "COLUMN", "VALUE", "STATUS_ICON", "MEASUREMENT_TIME"]],
            column_config={
                "TBL_NAME": "Table",
                "METRIC_NAME": "DMF",
                "COLUMN": "Column(s)",
                "VALUE": st.column_config.NumberColumn("Result", format="%d"),
                "STATUS_ICON": "Status",
                "MEASUREMENT_TIME": st.column_config.DatetimeColumn("Measured at", format="DD MMM YYYY HH:mm"),
            },
            hide_index=True,
            height=min(len(latest) * 40 + 40, 600),
        )

    col_health, col_row = st.columns(2)

    with col_health:
        with st.container(border=True):
            st.subheader("Health by table")
            st.caption("% of DMFs passing (value = 0) per table")

            non_info = latest[~latest["METRIC_NAME"].isin(["ROW_COUNT", "FRESHNESS"])].copy()
            if len(non_info) > 0:
                health_by_table = non_info.groupby("TBL_NAME").agg(
                    TOTAL=("VALUE", "count"),
                    PASSING=("VALUE", lambda x: (x == 0).sum()),
                ).reset_index()
                health_by_table["HEALTH_PCT"] = round(health_by_table["PASSING"] / health_by_table["TOTAL"] * 100, 1)
                health_by_table["BAR_COLOR"] = health_by_table["HEALTH_PCT"].apply(
                    lambda v: "#00703c" if v == 100 else ("#f47738" if v >= 80 else "#d4351c")
                )

                bar = (
                    alt.Chart(health_by_table)
                    .mark_bar(cornerRadiusEnd=4)
                    .encode(
                        x=alt.X("HEALTH_PCT:Q", title="Health %", scale=alt.Scale(domain=[0, 105])),
                        y=alt.Y("TBL_NAME:N", title="", sort="-x"),
                        color=alt.Color("BAR_COLOR:N", scale=None),
                        tooltip=[
                            alt.Tooltip("TBL_NAME:N", title="Table"),
                            alt.Tooltip("HEALTH_PCT:Q", title="Health %", format=".1f"),
                            alt.Tooltip("PASSING:Q", title="Passing"),
                            alt.Tooltip("TOTAL:Q", title="Total DMFs"),
                        ],
                    )
                    .properties(height=max(len(health_by_table) * 45, 200))
                )
                st.altair_chart(bar)

    with col_row:
        with st.container(border=True):
            st.subheader("Row counts")
            st.caption("Current row counts from ROW_COUNT DMF")

            row_counts = latest[latest["METRIC_NAME"] == "ROW_COUNT"].copy()
            if len(row_counts) > 0:
                row_counts["VALUE"] = row_counts["VALUE"].astype(int)
                bar = (
                    alt.Chart(row_counts)
                    .mark_bar(cornerRadiusEnd=4, color="#1d70b8")
                    .encode(
                        x=alt.X("VALUE:Q", title="Row count"),
                        y=alt.Y("TBL_NAME:N", title="", sort="-x"),
                        tooltip=[
                            alt.Tooltip("TBL_NAME:N", title="Table"),
                            alt.Tooltip("VALUE:Q", title="Rows", format=","),
                        ],
                    )
                    .properties(height=max(len(row_counts) * 45, 200))
                )
                st.altair_chart(bar)

    with st.container(border=True):
        st.subheader("DMF coverage by type")
        st.caption("Breakdown of attached DMFs by metric type")

        if len(inventory) > 0:
            dmf_counts = inventory.groupby("METRIC_NAME").size().reset_index(name="COUNT")
            pie = (
                alt.Chart(dmf_counts)
                .mark_arc(innerRadius=50)
                .encode(
                    theta=alt.Theta("COUNT:Q"),
                    color=alt.Color("METRIC_NAME:N", title="DMF Type"),
                    tooltip=["METRIC_NAME", "COUNT"],
                )
                .properties(height=300)
            )
            st.altair_chart(pie)
else:
    st.info(
        "DMFs have been attached and are scheduled to run on next data change. "
        "Results will appear here after the first measurement completes (typically 1-2 minutes).",
        icon=":material/hourglass_empty:",
    )

with st.container(border=True):
    st.subheader("How DMFs work")
    st.markdown("""
- **Data Metric Functions (DMFs)** run automatically whenever the underlying table data changes
- **Built-in DMFs** include `NULL_COUNT`, `ROW_COUNT`, `FRESHNESS`, `DUPLICATE_COUNT`, and `ACCEPTED_VALUES`
- **Custom DMFs** check domain-specific rules (e.g. no duplicate period+operator combinations)
- **Health score** = percentage of quality DMFs returning 0 (no issues). `ROW_COUNT` and `FRESHNESS` are informational only
- Results are stored in `SNOWFLAKE.LOCAL.DATA_QUALITY_MONITORING_RESULTS()` and visualised here
""")

    st.caption("Navigate to any table in Snowsight → Data Quality tab to see the full monitoring dashboard, alert configuration, and quality history.")


