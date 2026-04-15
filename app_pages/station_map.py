import json
import pathlib
import streamlit as st
import altair as alt
import pandas as pd
import pydeck as pdk
import requests
from app_pages.styling import inject_gov_uk_css
from app_pages.queries import load_stations, load_ppm_summary

UK_COASTLINE_URL = "https://raw.githubusercontent.com/yorkirich/UK-Coastline/main/uk%20coastline%20simplified.geojson"
RAIL_LINES_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "gb_rail_lines.geojson"

@st.cache_data(ttl=86400)
def _load_coastline():
    try:
        resp = requests.get(UK_COASTLINE_URL, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None

@st.cache_data(ttl=86400)
def _load_rail_lines():
    try:
        with open(RAIL_LINES_PATH) as f:
            return json.load(f)
    except Exception:
        return None

inject_gov_uk_css()

st.title("Station network map")
st.caption("3,300+ railway stations across Great Britain — coloured by region")

stations = load_stations()

if len(stations) == 0:
    st.warning("No station data available.", icon=":material/warning:")
    st.stop()

REGION_COLORS = {
    "London": [213, 0, 0],
    "South East": [0, 112, 60],
    "Scotland": [29, 112, 184],
    "North West": [244, 119, 56],
    "Wales": [212, 53, 28],
    "Eastern": [80, 90, 95],
    "South West": [21, 129, 135],
    "Yorkshire and the Humber": [84, 49, 159],
    "West Midlands": [202, 53, 124],
    "East Midlands": [0, 48, 120],
    "North East": [15, 122, 82],
}

stations["COLOR_R"] = stations["REGION"].map(lambda r: REGION_COLORS.get(r, [128, 128, 128])[0])
stations["COLOR_G"] = stations["REGION"].map(lambda r: REGION_COLORS.get(r, [128, 128, 128])[1])
stations["COLOR_B"] = stations["REGION"].map(lambda r: REGION_COLORS.get(r, [128, 128, 128])[2])

total_stations = len(stations)
regions = stations["REGION"].nunique()
countries = stations["COUNTRY"].nunique()

with st.container(horizontal=True):
    st.metric("Total stations", f"{total_stations:,}", border=True)
    st.metric("Regions", regions, border=True)
    st.metric("Countries", countries, border=True)

st.divider()

with st.sidebar:
    selected_regions = st.multiselect(
        "Filter by region",
        sorted(stations["REGION"].dropna().unique()),
        default=[],
        key="map_regions",
    )
    map_style = st.radio("Map style", ["Scatter", "Heatmap", "Hexbin"], index=0)

filtered = stations if not selected_regions else stations[stations["REGION"].isin(selected_regions)]

with st.container(border=True):
    if map_style == "Scatter":
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=filtered,
            get_position=["LONGITUDE", "LATITUDE"],
            get_color=["COLOR_R", "COLOR_G", "COLOR_B", 200],
            get_radius=800,
            pickable=True,
            auto_highlight=True,
        )
    elif map_style == "Heatmap":
        layer = pdk.Layer(
            "HeatmapLayer",
            data=filtered,
            get_position=["LONGITUDE", "LATITUDE"],
            get_weight=1,
            radiusPixels=30,
            opacity=0.6,
        )
    else:
        layer = pdk.Layer(
            "HexagonLayer",
            data=filtered,
            get_position=["LONGITUDE", "LATITUDE"],
            radius=5000,
            elevation_scale=50,
            elevation_range=[0, 3000],
            pickable=True,
            extruded=True,
        )

    view = pdk.ViewState(
        latitude=54.0,
        longitude=-2.5,
        zoom=5.3,
        pitch=30 if map_style == "Hexbin" else 0,
    )

    coastline = _load_coastline()
    rail_lines = _load_rail_lines()
    layers = []
    if coastline:
        layers.append(pdk.Layer(
            "GeoJsonLayer",
            data=coastline,
            stroked=True,
            filled=False,
            get_line_color=[180, 180, 180, 120],
            line_width_min_pixels=1,
        ))
    if rail_lines:
        layers.append(pdk.Layer(
            "GeoJsonLayer",
            data=rail_lines,
            stroked=True,
            filled=False,
            get_line_color=[100, 140, 200, 100],
            line_width_min_pixels=1,
        ))
    layers.append(layer)

    st.pydeck_chart(pdk.Deck(
        layers=layers,
        initial_view_state=view,
        tooltip={"text": "{STATION_NAME}\n{REGION}, {COUNTY_UNITARY}\n{POSTCODE_DISTRICT}"},
        map_style="mapbox://styles/mapbox/dark-v11",
    ))

col_region, col_county = st.columns(2)

with col_region:
    with st.container(border=True):
        st.subheader("Stations by region")
        region_counts = filtered.groupby("REGION").size().reset_index(name="STATIONS").sort_values("STATIONS", ascending=False)
        region_counts["BAR_COLOR"] = region_counts["REGION"].map(
            lambda r: f"rgb({REGION_COLORS.get(r, [128,128,128])[0]},{REGION_COLORS.get(r, [128,128,128])[1]},{REGION_COLORS.get(r, [128,128,128])[2]})"
        )

        bar = (
            alt.Chart(region_counts)
            .mark_bar(cornerRadiusEnd=4)
            .encode(
                x=alt.X("STATIONS:Q", title="Number of stations"),
                y=alt.Y("REGION:N", title="", sort="-x"),
                color=alt.Color("BAR_COLOR:N", scale=None),
                tooltip=[
                    alt.Tooltip("REGION:N", title="Region"),
                    alt.Tooltip("STATIONS:Q", title="Stations"),
                ],
            )
            .properties(height=max(len(region_counts) * 35, 250))
        )
        st.altair_chart(bar)

with col_county:
    with st.container(border=True):
        st.subheader("Top 15 counties by stations")
        county_counts = (
            filtered.groupby("COUNTY_UNITARY").size()
            .reset_index(name="STATIONS")
            .sort_values("STATIONS", ascending=False)
            .head(15)
        )
        bar = (
            alt.Chart(county_counts)
            .mark_bar(cornerRadiusEnd=4, color="#1d70b8")
            .encode(
                x=alt.X("STATIONS:Q", title="Number of stations"),
                y=alt.Y("COUNTY_UNITARY:N", title="", sort="-x"),
                tooltip=["COUNTY_UNITARY", "STATIONS"],
            )
            .properties(height=max(len(county_counts) * 30, 250))
        )
        st.altair_chart(bar)

with st.container(border=True):
    st.subheader("Station data")
    st.dataframe(
        filtered[["STATION_NAME", "REGION", "COUNTY_UNITARY", "COUNTRY", "POSTCODE_DISTRICT", "LATITUDE", "LONGITUDE"]],
        column_config={
            "STATION_NAME": "Station",
            "REGION": "Region",
            "COUNTY_UNITARY": "County/Unitary",
            "COUNTRY": "Country",
            "POSTCODE_DISTRICT": "Postcode",
            "LATITUDE": st.column_config.NumberColumn("Lat", format="%.4f"),
            "LONGITUDE": st.column_config.NumberColumn("Lon", format="%.4f"),
        },
        hide_index=True,
        height=400,
    )
