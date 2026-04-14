import streamlit as st

st.set_page_config(
    page_title="GB Rail Performance — Global Comparison",
    page_icon=":material/train:",
    layout="wide",
)

conn = st.connection("snowflake")

if "conn" not in st.session_state:
    st.session_state.conn = conn

page = st.navigation(
    {
        "": [
            st.Page("app_pages/international.py", title="Global comparison", icon=":material/public:", default=True),
        ],
        "GB Analysis": [
            st.Page("app_pages/overview.py", title="PPM overview", icon=":material/dashboard:"),
            st.Page("app_pages/operators.py", title="Operator drill-down", icon=":material/compare_arrows:"),
            st.Page("app_pages/delay_causes.py", title="Delay causes", icon=":material/schedule:"),
            st.Page("app_pages/cancellations.py", title="Cancellations", icon=":material/cancel:"),
            st.Page("app_pages/station_map.py", title="Station map", icon=":material/map:"),
        ],
        "Intelligence": [
            st.Page("app_pages/ask_data.py", title="Ask the data", icon=":material/chat:"),
        ],
        "Reference": [
            st.Page("app_pages/data_quality.py", title="Data quality", icon=":material/verified:"),
            st.Page("app_pages/about.py", title="About", icon=":material/info:"),
        ],
    },
    position="sidebar",
)

page.run()
