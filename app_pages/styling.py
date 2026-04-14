import re
import streamlit as st


GOV_UK_CSS = """
<style>
[data-testid="stButton"] button[kind="primary"] {
    background-color: #0f7a52 !important;
    border-color: #0f7a52 !important;
    color: #ffffff !important;
}
[data-testid="stButton"] button[kind="primary"]:hover {
    background-color: #0b5c3e !important;
    border-color: #0b5c3e !important;
}
[data-testid="stButton"] button[kind="secondary"] {
    background-color: #ca3535 !important;
    border-color: #ca3535 !important;
    color: #ffffff !important;
}
*:focus-visible {
    outline: 3px solid #ffdd00 !important;
    outline-offset: 0 !important;
}
</style>
"""


def inject_gov_uk_css():
    st.markdown(GOV_UK_CSS, unsafe_allow_html=True)


def rag_badge(status: str) -> str:
    mapping = {
        "GREEN": ":green-badge[GREEN]",
        "AMBER": ":orange-badge[AMBER]",
        "RED": ":red-badge[RED]",
    }
    return mapping.get(status, f":grey-badge[{status}]")


def short_period(time_period: str) -> str:
    m = re.search(r"\(Period (\d+)\)", time_period)
    if m:
        return f"P{int(m.group(1)):02d}"
    return time_period


def short_fy(financial_year: str) -> str:
    m = re.match(r"Apr (\d{4}) to Mar (\d{4})", financial_year)
    if m:
        return f"FY{m.group(1)[2:]}/{m.group(2)[2:]}"
    return financial_year
