import streamlit as st
import pandas as pd

def show():
    st.header("🧾 Capex & Opex")

    results = st.session_state.get("results")
    if not results:
        st.info("Run a scenario to see results.")
        return

    fin = results.get("Financial", {})
    cap = fin.get("capex_breakdown", {})
    opx = fin.get("opex_breakdown", {})

    if cap:
        st.subheader("Capex Breakdown")
        cdf = pd.DataFrame([{"Category": k, "Amount ($)": v} for k, v in cap.items()])
        st.dataframe(cdf, use_container_width=True)
    else:
        st.info("No Capex breakdown found in results.")

    if opx:
        st.subheader("Opex (Annual)")
        odf = pd.DataFrame([{"Category": k, "Amount ($/yr)": v} for k, v in opx.items()])
        st.dataframe(odf, use_container_width=True)
    else:
        st.info("No Opex breakdown found in results.")
