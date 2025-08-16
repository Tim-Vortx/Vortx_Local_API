import streamlit as st
import pandas as pd
from utils.transform import to_daily_series
from utils.charts import daily_ops_chart

def show():
    st.header("🕘 24-Hour Operations")

    results = st.session_state.get("results")
    if not results:
        st.info("Run a scenario to see results.")
        return

    tph = results.get("Settings", {}).get("time_steps_per_hour", 1)
    total_hours = len(results.get("ElectricLoad", {}).get("load_series_kw", [])) or (8760 * tph)
    max_day = max(0, total_hours // (24 * tph) - 1)

    day = st.slider(
        "Day of year",
        min_value=0,
        max_value=max_day,
        value=st.session_state.get("daily_ops_day", 0),
        key="daily_ops_day",
    )
    df = to_daily_series(results, day_index=day, tph=tph)

    st.altair_chart(daily_ops_chart(df), use_container_width=True)
    st.caption("Stacked supply-to-load with load line. Thin overlays (charging/exports) hidden for clarity.")
