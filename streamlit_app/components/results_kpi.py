import streamlit as st

def _fmt_money(x):
    try:
        return f"${x:,.0f}"
    except:
        return "-"

def show():
    st.header("📈 KPI Summary")

    results = st.session_state.get("results")
    if not results:
        st.info("Run a scenario to see results.")
        return

    fin = results.get("Financial", {})
    emi = results.get("Emissions", {})
    kpi_cols = st.columns(6)
    kpi_cols[0].metric("Total Capex", _fmt_money(fin.get("capital_cost", 0)))
    kpi_cols[1].metric("Annual Savings", _fmt_money(fin.get("annual_savings", 0)))
    kpi_cols[2].metric("NPV", _fmt_money(fin.get("npv", 0)))
    kpi_cols[3].metric("Payback (yrs)", f"{fin.get('payback_years', 0):.1f}")
    kpi_cols[4].metric("CO₂ Δ (t/yr)", f"{emi.get('annual_co2_change_tons', 0):,.0f}")
    kpi_cols[5].metric("LCOE ($/kWh)", f"{fin.get('lcoe', 0):.03f}")
