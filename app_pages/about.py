import streamlit as st
from app_pages.styling import inject_gov_uk_css
from app_pages.queries import load_object_inventory, load_cost_tracker

inject_gov_uk_css()

st.title("About this platform")

st.markdown("""
This is the **DfT PPM Intelligence Platform** — a Snowflake-native analytics solution for 
monitoring and understanding Great Britain's rail punctuality through the 
**Public Performance Measure (PPM)**.
""")

tab_arch, tab_data, tab_cost, tab_glossary = st.tabs([
    ":material/architecture: Architecture",
    ":material/database: Data sources",
    ":material/payments: Cost controls",
    ":material/menu_book: Glossary",
])

with tab_arch:
    st.subheader("Platform architecture")

    st.markdown("""
    ```
    ┌─────────────────────────────────────────────────────────────┐
    │                    SNOWFLAKE ACCOUNT                        │
    │                 SFSEEUROPE-US_WEST_DEMO_PG                  │
    │                                                             │
    │  ┌─────────────────── DFT_PPM ───────────────────────────┐  │
    │  │                                                       │  │
    │  │  RAW                    PROCESSED                     │  │
    │  │  ┌──────────────┐      ┌──────────────────────┐       │  │
    │  │  │ ORR tables   │─────▶│ PPM_BY_OPERATOR      │       │  │
    │  │  │ (5 tables)   │      │ DELAY_CAUSES_SUMMARY │       │  │
    │  │  │              │      │ CANCELLATIONS_BY_OP  │       │  │
    │  │  ├──────────────┤      └──────────┬───────────┘       │  │
    │  │  │ Marketplace  │                 │                   │  │
    │  │  │ views (3)    │                 ▼                   │  │
    │  │  │ • Stations   │      ANALYTICS                      │  │
    │  │  │ • Regions    │      ┌──────────────────────┐       │  │
    │  │  │ • Weather    │      │ PPM_DASHBOARD_SUMMARY│       │  │
    │  │  ├──────────────┤      │ COST_TRACKER         │       │  │
    │  │  │ International│      │ INTL_PPM_LEAGUE      │       │  │
    │  │  │ benchmarks   │      └──────────────────────┘       │  │
    │  │  └──────────────┘                                     │  │
    │  │                                                       │  │
    │  │  FEATURES (reserved for ML feature store)             │  │
    │  └───────────────────────────────────────────────────────┘  │
    │                                                             │
    │  ┌─ DFT_PPM_WH ──────────────────────────────────────────┐  │
    │  │ X-Small · 30s auto-suspend · 20 credit/month monitor  │  │
    │  └───────────────────────────────────────────────────────┘  │
    │                                                             │
    │  ┌─ Scheduled Task ──────────────────────────────────────┐  │
    │  │ REFRESH_PPM_SUMMARY · Daily 06:00 UTC · ~0.02 cr/day │  │
    │  └───────────────────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────────────────┘
    ```
    """)

    st.markdown("##### Design principles")
    st.markdown("""
- **Cost-first architecture** — No Dynamic Tables, no Cortex Search Services, no Snowpipe. 
  Everything is batch-loaded and on-demand. The only ongoing cost is one daily Task (~0.5 credits/month).
- **Marketplace-first data** — OS Open Names, Boundary Line, and Met Office weather are 
  consumed as shared views, not ingested copies. Zero storage cost, always up to date.
- **Minimal automation** — One scheduled Task refreshes the dashboard summary daily. 
  All other data refreshes are manual (re-run the ORR scraper, PUT/COPY INTO).
- **Zero cost when idle** — If nobody queries this platform for a month, the cost is 
  effectively £0 (aside from the daily Task at ~0.02 credits).
    """)

    st.markdown("##### Object inventory")
    inventory = load_object_inventory()
    st.dataframe(
        inventory.rename(columns={
            "TABLE_SCHEMA": "Schema",
            "TABLE_NAME": "Object",
            "TABLE_TYPE": "Type",
            "ROW_COUNT": "Rows",
        }),
        column_config={
            "Rows": st.column_config.NumberColumn(format="%,.0f"),
        },
        hide_index=True,
    )

with tab_data:
    st.subheader("Data sources")

    st.markdown("##### ORR Data Portal (Office of Rail and Road)")
    st.markdown("""
| Table | Description | Rows | Frequency |
|-------|-------------|------|-----------|
| `ORR_PPM_BY_OPERATOR` | PPM % by 30 operators (wide format) | 90 | 4-weekly (periodic) |
| `ORR_DELAY_MINUTES_BY_CAUSE` | Delay minutes by operator × 15 cause categories | 2,116 | 4-weekly |
| `ORR_CASL_BY_OPERATOR` | Cancelled & Significantly Late % by operator | 90 | 4-weekly |
| `ORR_CANCELLATIONS_BY_OPERATOR` | Trains planned / part / full cancelled | 2,385 | 4-weekly |
| `ORR_PUNCTUALITY_BY_OPERATOR` | Station stop punctuality (T2-3 through T2-30) | 4,063 | 4-weekly |

Source: [dataportal.orr.gov.uk](https://dataportal.orr.gov.uk) · Open Government Licence v3.0
    """)

    st.markdown("##### Snowflake Marketplace (zero-cost shared views)")
    st.markdown("""
| View | Source | Description |
|------|--------|-------------|
| `RAILWAY_STATIONS` | OS Open Names | 3,323 GB railway stations with coordinates |
| `REGIONS` | OS Boundary Line | 2,707 administrative regions (English regions + countries) |
| `WEATHER_WARNINGS` | NSWWS (Met Office) | Active weather warnings for transport |
    """)

    st.markdown("##### International benchmarks (manual seed)")
    st.markdown("""
| Country | Railway | OTP % | Threshold |
|---------|---------|-------|-----------|
| Japan | JR | ~99.0% | 1 minute |
| Switzerland | SBB | 94.1% | 3 minutes |
| Netherlands | NS | 89.4% | 5 minutes |
| Great Britain | National Rail | 81.5% | 5/10 minutes |

Sources: SBB reporting portal, NS annual report, JR Central IR publications, ORR
    """)

    st.markdown("##### Data refresh process")
    st.markdown("""
1. **ORR data**: Run the Python scraper (`extract_orr_ppm.py`) to download latest periodic tables
2. **PUT** the CSVs to `@DFT_PPM.RAW.ORR_STAGE`
3. **COPY INTO** the corresponding RAW tables
4. The daily Task automatically refreshes `PPM_DASHBOARD_SUMMARY` at 06:00 UTC
5. Marketplace views are always live — no refresh needed
    """)

with tab_cost:
    st.subheader("Cost controls")

    st.markdown("""
    | Control | Setting |
    |---------|---------|
    | **Warehouse** | `DFT_PPM_WH` — X-Small (1 credit/hour active) |
    | **Auto-suspend** | 30 seconds — suspends rapidly when idle |
    | **Resource monitor** | `DFT_PPM_COST_MONITOR` — 20 credits/month, suspend at 100% |
    | **Scheduled Task** | 1 daily Task — ~0.02 credits/day (~0.6 credits/month) |
    | **Dynamic Tables** | None — avoids continuous polling costs |
    | **Cortex Search** | None — avoids always-on index costs |
    | **Snowpipe** | None — batch PUT/COPY only |
    """)

    st.markdown("##### Credit usage")
    try:
        costs = load_cost_tracker()
        if len(costs) > 0:
            st.dataframe(costs, hide_index=True)
        else:
            st.caption("No credit usage data available yet.")
    except Exception:
        st.caption("Cost tracker view not available — check ACCOUNT_USAGE access.")

    st.markdown("##### Estimated monthly cost")
    st.markdown("""
    | Component | Credits/month | Notes |
    |-----------|---------------|-------|
    | Daily Task | ~0.6 | 30 runs × ~0.02 credits each |
    | Ad-hoc queries | ~1-3 | Depends on dashboard usage |
    | Storage | <0.1 | ~10 MB total across all tables |
    | **Total** | **~2-4** | **~$4-8/month at standard pricing** |
    """)

with tab_glossary:
    st.subheader("Glossary")

    st.markdown("""
| Term | Definition |
|------|-----------|
| **PPM** | **Public Performance Measure** — the official GB rail punctuality metric. A train is "on time" if it arrives at its final destination within 5 minutes (regional/LSE) or 10 minutes (long distance) of scheduled time. |
| **CaSL** | **Cancelled and Significantly Late** — companion metric to PPM. Measures % of trains cancelled or arriving 30+ minutes late. |
| **TOC** | **Train Operating Company** — the franchised or open access operator running passenger services (e.g. Avanti West Coast, ScotRail). |
| **NR** | **Network Rail** — owns and maintains GB rail infrastructure (track, signalling, stations). |
| **ORR** | **Office of Rail and Road** — independent regulator. Publishes official performance statistics. |
| **Period** | Rail industry uses 13 four-weekly periods per financial year (Apr–Mar), not calendar months. |
| **RAG** | **Red/Amber/Green** status. Green ≥ 92.5%, Amber ≥ 85%, Red < 85%. |
| **MAA** | **Moving Annual Average** — 13-period rolling average to smooth seasonal variation. |
| **Delay attribution** | Process of assigning each delay to a responsible party (NR infrastructure, TOC fleet, weather, etc.). |
| **LSE** | **London and South East** sector — commuter services with 5-minute on-time threshold. |
| **XS warehouse** | Snowflake X-Small warehouse — smallest compute size at 1 credit per hour when active. |
    """)

    st.markdown("##### PPM thresholds by sector")
    st.markdown("""
| Sector | On-time threshold |
|--------|-------------------|
| London and South East | ≤ 5 minutes late |
| Regional | ≤ 5 minutes late |
| Scotland | ≤ 5 minutes late |
| Long Distance | ≤ 10 minutes late |
    """)

st.caption("Built on Snowflake · Data sourced under Open Government Licence v3.0")
