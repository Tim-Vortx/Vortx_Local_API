import streamlit as st


def show():
    scn = st.session_state.setdefault("scenario", {})
    fin = scn.setdefault("Financial", {})
    st.subheader("💵 Financials & Incentives")

    c1, c2, c3 = st.columns(3)
    with c1:
        fin["analysis_years"] = st.number_input("Analysis years", value=fin.get("analysis_years", 25), step=1, key="fin_years")
    with c2:
        fin["offtaker_discount_rate_fraction"] = st.number_input("Discount rate (fraction)", value=fin.get("offtaker_discount_rate_fraction", 0.08), step=0.01, format="%.3f", key="fin_dr")
    with c3:
        fin["elec_cost_escalation_rate_fraction"] = st.number_input("Elec cost escalation (fraction)", value=fin.get("elec_cost_escalation_rate_fraction", 0.025), step=0.005, format="%.3f", key="fin_escal")

    st.markdown("**Incentives (simplified)**")
    c4, c5, c6 = st.columns(3)
    with c4:
        fin["itc"] = st.number_input("ITC fraction (0..0.5)", value=fin.get("itc", 0.30), step=0.05, min_value=0.0, max_value=0.5, key="fin_itc")
    with c5:
        fin["macrs_option_years"] = st.selectbox("MACRS", options=[5, 7], index=0 if fin.get("macrs_option_years", 5) == 5 else 1, key="fin_macrs")
    with c6:
        fin["bonus_depreciation_fraction"] = st.number_input("Bonus depreciation (fraction)", value=fin.get("bonus_depreciation_fraction", 0.0), step=0.1, min_value=0.0, max_value=1.0, key="fin_bonus")

    fin["capital_incentive"] = st.number_input("SGIP / Capital incentive ($)", value=fin.get("capital_incentive", 0.0), step=1000.0, key="fin_sgip")

