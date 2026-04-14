import streamlit as st
import altair as alt
import pandas as pd
from app_pages.styling import inject_gov_uk_css
from app_pages.queries import load_international, load_ppm_summary

inject_gov_uk_css()

st.title("How does GB rail compare to the world?")

intl = load_international()

if len(intl) == 0:
    st.warning("No international benchmark data available.", icon=":material/warning:")
    st.stop()

gb = intl[intl["COUNTRY"] == "Great Britain"]
gb_ppm = gb["PPM_PERCENT"].values[0] if len(gb) > 0 else 0
gb_position = int(gb["LEAGUE_POSITION"].values[0]) if len(gb) > 0 else 0
total_countries = len(intl)
best = intl.head(1)
best_country = best["COUNTRY"].values[0]
best_ppm = best["PPM_PERCENT"].values[0]
gap_to_best = round(best_ppm - gb_ppm, 1)

above_gb = intl[intl["PPM_PERCENT"] > gb_ppm]
below_gb = intl[intl["PPM_PERCENT"] < gb_ppm]

with st.container(horizontal=True):
    st.metric("GB league position", f"{gb_position}th of {total_countries}", border=True)
    st.metric("GB composite PPM", f"{gb_ppm}%", border=True)
    st.metric("Gap to 1st", f"-{gap_to_best}pp", help="pp = percentage points", border=True)

st.divider()

intl["IS_GB"] = intl["COUNTRY"] == "Great Britain"
intl["BAR_COLOR"] = intl.apply(
    lambda r: "#d4351c" if r["COUNTRY"] == "Great Britain"
    else ("#00703c" if r["PPM_PERCENT"] >= 90 else ("#f47738" if r["PPM_PERCENT"] >= 80 else "#b1b4b6")),
    axis=1,
)
intl["LABEL"] = intl.apply(
    lambda r: f"{r['COUNTRY']}  ({r['RAILWAY']})" if r["COUNTRY"] != "Great Britain"
    else f"{r['COUNTRY']}  (National Rail)",
    axis=1,
)

sort_order = intl.sort_values("PPM_PERCENT", ascending=False)["LABEL"].tolist()

with st.container(border=True):
    st.subheader("Global punctuality league table")
    st.caption("Ranked by on-time performance percentage — GB highlighted in red")

    bars = (
        alt.Chart(intl)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("PPM_PERCENT:Q", title="On-time performance %", scale=alt.Scale(domain=[0, 105])),
            y=alt.Y("LABEL:N", title="", sort=sort_order),
            color=alt.Color("BAR_COLOR:N", scale=None),
            tooltip=[
                alt.Tooltip("COUNTRY:N", title="Country"),
                alt.Tooltip("RAILWAY:N", title="Railway"),
                alt.Tooltip("PPM_PERCENT:Q", title="PPM %", format=".1f"),
                alt.Tooltip("THRESHOLD_MINUTES:Q", title="Threshold (mins)"),
                alt.Tooltip("METRIC:N", title="Metric"),
                alt.Tooltip("LEAGUE_POSITION:Q", title="Rank"),
            ],
        )
    )

    labels = (
        alt.Chart(intl)
        .mark_text(align="left", dx=5, fontSize=13, fontWeight="bold")
        .encode(
            x=alt.X("PPM_PERCENT:Q"),
            y=alt.Y("LABEL:N", sort=sort_order),
            text=alt.Text("PPM_PERCENT:Q", format=".1f"),
            color=alt.Color("BAR_COLOR:N", scale=None),
        )
    )

    gb_rule = (
        alt.Chart(pd.DataFrame({"x": [gb_ppm]}))
        .mark_rule(strokeDash=[6, 4], strokeWidth=2, color="#d4351c")
        .encode(x="x:Q")
    )

    st.altair_chart(
        (bars + labels + gb_rule).properties(height=max(total_countries * 42, 350)),
    )

col_gap, col_threshold = st.columns(2)

with col_gap:
    with st.container(border=True):
        st.subheader("Gap to GB")
        st.caption("Percentage points ahead (+) or behind (-) Great Britain")

        gap_df = intl[intl["COUNTRY"] != "Great Britain"].copy()
        gap_df["GAP_COLOR"] = gap_df["GAP_TO_GB_PPM"].apply(
            lambda x: "#d4351c" if x > 0 else "#00703c"
        )
        gap_sort = gap_df.sort_values("GAP_TO_GB_PPM", ascending=True)["LABEL"].tolist()

        gap_bars = (
            alt.Chart(gap_df)
            .mark_bar(cornerRadiusEnd=3)
            .encode(
                x=alt.X("GAP_TO_GB_PPM:Q", title="Gap (pp)"),
                y=alt.Y("LABEL:N", title="", sort=gap_sort),
                color=alt.Color("GAP_COLOR:N", scale=None),
                tooltip=[
                    alt.Tooltip("COUNTRY:N", title="Country"),
                    alt.Tooltip("GAP_TO_GB_PPM:Q", title="Gap (pp)", format="+.1f"),
                    alt.Tooltip("PPM_PERCENT:Q", title="Their PPM %", format=".1f"),
                ],
            )
            .properties(height=max((total_countries - 1) * 35, 300))
        )

        zero_rule = (
            alt.Chart(pd.DataFrame({"x": [0]}))
            .mark_rule(color="#0b0c0c", strokeWidth=1)
            .encode(x="x:Q")
        )

        st.altair_chart(gap_bars + zero_rule)

COUNTRY_FLAGS = {
    "Taiwan": "\U0001F1F9\U0001F1FC", "Japan": "\U0001F1EF\U0001F1F5",
    "South Korea": "\U0001F1F0\U0001F1F7", "Switzerland": "\U0001F1E8\U0001F1ED",
    "Spain": "\U0001F1EA\U0001F1F8", "France": "\U0001F1EB\U0001F1F7",
    "Netherlands": "\U0001F1F3\U0001F1F1", "Italy": "\U0001F1EE\U0001F1F9",
    "Finland": "\U0001F1EB\U0001F1EE", "Austria": "\U0001F1E6\U0001F1F9",
    "Denmark": "\U0001F1E9\U0001F1F0", "Great Britain": "\U0001F1EC\U0001F1E7",
    "Sweden": "\U0001F1F8\U0001F1EA", "Germany": "\U0001F1E9\U0001F1EA",
}

with col_threshold:
    with st.container(border=True):
        st.subheader("Threshold comparison")
        st.caption("Different countries use different 'on-time' definitions")

        threshold_df = intl[intl["THRESHOLD_MINUTES"].notna()].copy()
        threshold_df["THRESHOLD_MINUTES"] = threshold_df["THRESHOLD_MINUTES"].astype(int)
        threshold_df["FLAG"] = threshold_df["COUNTRY"].map(COUNTRY_FLAGS).fillna("")

        bubble = (
            alt.Chart(threshold_df)
            .mark_circle(opacity=0.8)
            .encode(
                x=alt.X("THRESHOLD_MINUTES:Q", title="On-time threshold (minutes)", scale=alt.Scale(domain=[0, 12])),
                y=alt.Y("PPM_PERCENT:Q", title="PPM %", scale=alt.Scale(domain=[55, 105])),
                size=alt.Size("PPM_PERCENT:Q", legend=None, scale=alt.Scale(range=[200, 1200])),
                color=alt.Color("BAR_COLOR:N", scale=None),
                tooltip=[
                    alt.Tooltip("COUNTRY:N"),
                    alt.Tooltip("RAILWAY:N"),
                    alt.Tooltip("PPM_PERCENT:Q", format=".1f"),
                    alt.Tooltip("THRESHOLD_MINUTES:Q", title="Threshold (mins)"),
                ],
            )
            .properties(height=400)
        )

        flag_text = (
            alt.Chart(threshold_df)
            .mark_text(fontSize=18, baseline="middle")
            .encode(
                x=alt.X("THRESHOLD_MINUTES:Q"),
                y=alt.Y("PPM_PERCENT:Q"),
                text="FLAG:N",
            )
        )

        st.altair_chart(bubble + flag_text)

with st.container(border=True):
    st.subheader("Full benchmark data")
    st.dataframe(
        intl[["LEAGUE_POSITION", "COUNTRY", "RAILWAY", "PPM_PERCENT", "THRESHOLD_MINUTES", "PERFORMANCE_CATEGORY", "GAP_TO_GB_PPM", "NOTES"]],
        column_config={
            "LEAGUE_POSITION": st.column_config.NumberColumn("Rank", format="%d"),
            "PPM_PERCENT": st.column_config.NumberColumn("PPM %", format="%.1f"),
            "THRESHOLD_MINUTES": st.column_config.NumberColumn("Threshold (mins)"),
            "GAP_TO_GB_PPM": st.column_config.NumberColumn("Gap to GB (pp)", format="%+.1f"),
            "COUNTRY": "Country",
            "RAILWAY": "Railway",
            "PERFORMANCE_CATEGORY": "Category",
            "NOTES": "Notes",
        },
        hide_index=True,
        height=530,
    )

with st.container(border=True):
    st.subheader("Key takeaways")
    gb_cat = gb["PERFORMANCE_CATEGORY"].values[0] if len(gb) > 0 else "N/A"
    st.markdown(f"""
- GB is rated **{gb_cat}** — sitting **{gb_position}th of {total_countries}** in the global league, **{gap_to_best}pp** behind {best_country}
- Only **{len(below_gb)}** country/countries perform worse than GB: {', '.join(below_gb['COUNTRY'].tolist()) if len(below_gb) > 0 else 'none'}
- **Threshold bias matters** — Japan's 99% is measured at 1 minute; GB uses 5/10 minutes and still lags
- A **5pp improvement** would move GB from {gb_position}th to roughly {max(1, gb_position - 3)}th, saving ~95,000 delayed journeys per quarter
- Germany (DB) at 64.2% shows that even wealthy nations can have poor rail punctuality
- **Why 14 countries?** These are the major European and East Asian rail networks with publicly comparable on-time data. Many countries do not publish standardised punctuality figures.
""")

    st.caption("pp = percentage points. Comparisons should be treated with caution — different threshold definitions "
        "(1–10 minutes), network sizes, and geographic conditions affect these figures.")
