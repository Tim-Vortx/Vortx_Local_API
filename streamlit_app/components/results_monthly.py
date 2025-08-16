import streamlit as st
from utils.transform import monthly_rollup
from utils.charts import monthly_perf_chart

def show():
    st.header("📆 Monthly Performance & Savings")

    results = st.session_state.get("results")
    if not results:
        st.info("Run a scenario to see results.")
        return

    m = monthly_rollup(results)
    st.dataframe(m, use_container_width=True)
    st.altair_chart(monthly_perf_chart(m), use_container_width=True)
