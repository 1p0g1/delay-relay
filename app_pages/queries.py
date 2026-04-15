import base64
import streamlit as st
import pandas as pd
import snowflake.connector
from datetime import timedelta

TTL = timedelta(minutes=30)


@st.cache_resource
def _init_connection():
    try:
        secrets = st.secrets["connections"]["snowflake"]
    except (KeyError, FileNotFoundError):
        return st.connection("snowflake").raw_connection
    params = {k: str(v) for k, v in dict(secrets).items()}
    params.pop("authenticator", None)
    if "private_key" in params:
        params.pop("private_key_file_pwd", None)
        params["private_key"] = base64.b64decode(params["private_key"])
    elif "private_key_file" in params:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        pwd = params.pop("private_key_file_pwd", None)
        with open(params.pop("private_key_file"), "rb") as f:
            p_key = serialization.load_pem_private_key(
                f.read(),
                password=pwd.encode() if pwd else None,
                backend=default_backend(),
            )
        params["private_key"] = p_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    return snowflake.connector.connect(**params)


def get_conn():
    return _init_connection()


def _query(sql, params=None) -> pd.DataFrame:
    cur = get_conn().cursor()
    try:
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        cur.close()


@st.cache_data(ttl=TTL)
def load_ppm_summary() -> pd.DataFrame:
    return _query("""
        SELECT OPERATOR, CATEGORY, LATEST_PERIOD, LATEST_PPM, PREVIOUS_PPM,
               PPM_CHANGE, RAG_STATUS, REFRESHED_AT
        FROM DFT_PPM.ANALYTICS.PPM_DASHBOARD_SUMMARY
        ORDER BY LATEST_PPM DESC
    """)


@st.cache_data(ttl=TTL)
def load_ppm_trend() -> pd.DataFrame:
    return _query("""
        SELECT TIME_PERIOD, FINANCIAL_YEAR, PERIOD_NUMBER, OPERATOR, CATEGORY, PPM_PERCENTAGE
        FROM DFT_PPM.PROCESSED.PPM_BY_OPERATOR
        ORDER BY TIME_PERIOD
    """)


@st.cache_data(ttl=TTL)
def load_delay_causes() -> pd.DataFrame:
    return _query("""
        SELECT TIME_PERIOD, FINANCIAL_YEAR, PERIOD_NUMBER, TRAIN_OPERATING_COMPANY,
               TOTAL_NR_CAUSED_DELAY_MINS, TOTAL_TOC_SELF_DELAY_MINS, TOTAL_TOC_OTHER_DELAY_MINS,
               WEATHER_DELAY_MINS, TRACK_DELAY_MINS, TOTAL_FLEET_DELAY_MINS, TOTAL_TRAINCREW_DELAY_MINS
        FROM DFT_PPM.PROCESSED.DELAY_CAUSES_SUMMARY
        ORDER BY TIME_PERIOD, TRAIN_OPERATING_COMPANY
    """)


@st.cache_data(ttl=TTL)
def load_cancellations() -> pd.DataFrame:
    return _query("""
        SELECT TIME_PERIOD, FINANCIAL_YEAR, PERIOD_NUMBER, OPERATOR,
               TRAINS_PLANNED, TRAINS_PART_CANCELLED, TRAINS_FULL_CANCELLED,
               CANCELLATION_NUMBER, CANCELLATIONS_PERCENTAGE, MAA_CANCELLATIONS_PERCENTAGE
        FROM DFT_PPM.PROCESSED.CANCELLATIONS_BY_OPERATOR
        ORDER BY TIME_PERIOD, OPERATOR
    """)


@st.cache_data(ttl=TTL)
def load_international() -> pd.DataFrame:
    return _query("""
        SELECT RAILWAY, COUNTRY, PPM_PERCENT, METRIC, THRESHOLD_MINUTES,
               PERFORMANCE_CATEGORY, NOTES, OPERATOR_COVERAGE, DATA_SOURCE,
               GB_BASELINE, GAP_TO_GB_PPM, LEAGUE_POSITION
        FROM DFT_PPM.ANALYTICS.INTERNATIONAL_PPM_LEAGUE
        ORDER BY PPM_PERCENT DESC
    """)


@st.cache_data(ttl=TTL)
def load_cost_tracker() -> pd.DataFrame:
    return _query("SELECT * FROM DFT_PPM.ANALYTICS.COST_TRACKER")


@st.cache_data(ttl=TTL)
def load_object_inventory() -> pd.DataFrame:
    return _query("""
        SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE, ROW_COUNT
        FROM DFT_PPM.INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA IN ('RAW', 'PROCESSED', 'ANALYTICS', 'FEATURES')
        ORDER BY TABLE_SCHEMA, TABLE_TYPE, TABLE_NAME
    """)


@st.cache_data(ttl=TTL)
def load_stations() -> pd.DataFrame:
    return _query("""
        SELECT STATION_NAME, LATITUDE, LONGITUDE, REGION, COUNTY_UNITARY, COUNTRY, POSTCODE_DISTRICT
        FROM DFT_PPM.RAW.RAILWAY_STATIONS
        WHERE LATITUDE IS NOT NULL AND LONGITUDE IS NOT NULL
    """)


@st.cache_data(ttl=timedelta(minutes=5))
def load_dq_results() -> pd.DataFrame:
    return _query("""
        SELECT * FROM DFT_PPM.ANALYTICS.DATA_QUALITY_RESULTS
        ORDER BY MEASUREMENT_TIME DESC
    """)


@st.cache_data(ttl=timedelta(minutes=5))
def load_dq_inventory() -> pd.DataFrame:
    tables = [
        'DFT_PPM.RAW.ORR_PUNCTUALITY_BY_OPERATOR',
        'DFT_PPM.RAW.ORR_CANCELLATIONS_BY_OPERATOR',
        'DFT_PPM.RAW.ORR_DELAY_MINUTES_BY_CAUSE',
        'DFT_PPM.RAW.INTERNATIONAL_BENCHMARKS',
        'DFT_PPM.RAW.ORR_PPM_BY_OPERATOR',
        'DFT_PPM.RAW.ORR_CASL_BY_OPERATOR',
        'DFT_PPM.ANALYTICS.PPM_DASHBOARD_SUMMARY',
    ]
    frames = []
    for tbl in tables:
        parts = tbl.split(".")
        try:
            df = _query(f"""
                SELECT
                  '{parts[1]}' AS TBL_SCHEMA,
                  '{parts[2]}' AS TBL_NAME,
                  METRIC_NAME,
                  METRIC_DATABASE_NAME,
                  METRIC_SCHEMA_NAME,
                  REF_ARGUMENTS,
                  SCHEDULE,
                  SCHEDULE_STATUS
                FROM TABLE(DFT_PPM.INFORMATION_SCHEMA.DATA_METRIC_FUNCTION_REFERENCES(
                  REF_ENTITY_NAME => '{tbl}',
                  REF_ENTITY_DOMAIN => 'TABLE'
                ))
            """)
            frames.append(df)
        except Exception:
            pass
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
