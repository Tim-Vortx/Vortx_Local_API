import streamlit as st
import pandas as pd

def show():
    st.header("🧪 Scenario Compare")

    st.info("Wire this to a `/batch` endpoint later. For now, this view expects multiple result dicts in session state.")
    results_list = st.session_state.get("scenario_results_list", [])  # list of dicts

    if not results_list:
        st.write("No scenarios loaded.")
        return

    rows = []
    for i, r in enumerate(results_list, start=1):
        fin = r.get("Financial", {})
        em  = r.get("Emissions", {})
        rows.append({
            "Scenario": f"S{i}",
            "Capex ($)": fin.get("capital_cost", 0),
            "Annual Savings ($/yr)": fin.get("annual_savings", 0),
            "NPV ($)": fin.get("npv", 0),
            "Payback (yrs)": fin.get("payback_years", 0),
            "Δ CO₂e (t/yr)": em.get("annual_co2_change_tons", 0),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
