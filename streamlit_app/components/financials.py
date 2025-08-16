import streamlit as st

def show():
    st.header("💵 Financial Inputs")

    # Use intermediate percent inputs (for user friendliness) then write
    # normalized fraction values into the session_state keys that the
    # validators/build pipeline expect.
    st.number_input("Discount Rate (%)", min_value=0.0, value=st.session_state.get("discount_rate_pct", 6.0), key="discount_rate_pct")
    st.number_input("Analysis Period (years)", min_value=1, value=st.session_state.get("analysis_years", 20), key="analysis_years")
    st.number_input("Inflation Rate (%)", min_value=0.0, value=st.session_state.get("inflation_rate_pct", 2.5), key="inflation_rate_pct")
    st.number_input("ITC (%)", min_value=0.0, value=st.session_state.get("itc_pct", 30.0), key="itc_pct")

    # Normalize percent -> fraction for downstream code
    try:
        # Discount rate: store as off-taker discount fraction
        pct = st.session_state.get("discount_rate_pct", 6.0)
        st.session_state["offtaker_discount_rate_fraction"] = float(pct) / 100.0
    except Exception:
        pass
    try:
        pct = st.session_state.get("inflation_rate_pct", 2.5)
        st.session_state["elec_cost_escalation_rate_fraction"] = float(pct) / 100.0
    except Exception:
        pass
    try:
        pct = st.session_state.get("itc_pct", 30.0)
        st.session_state["itc"] = float(pct) / 100.0
    except Exception:
        pass

