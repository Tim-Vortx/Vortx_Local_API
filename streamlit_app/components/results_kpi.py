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

    # If backend returned runtime/precompilation errors, surface them clearly
    msgs = results.get("Messages") if isinstance(results, dict) else None
    if isinstance(msgs, dict):
        errs = msgs.get("errors")
        if errs:
            st.error("Backend reported errors while running the model. See details below:")
            # errs may be a nested list (as we observed from Julia traces). Render safely.
            try:
                for i, item in enumerate(errs):
                    st.markdown(f"**Error {i+1}:**")
                    # If item is a list of strings, join them; else stringify
                    if isinstance(item, (list, tuple)):
                        st.code("\n".join([str(x) for x in item]))
                    else:
                        st.code(str(item))
            except Exception:
                st.text(str(errs))
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
