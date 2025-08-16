import streamlit as st

def show():
    st.header("🌿 Emissions & 🛡️ Resilience")

    results = st.session_state.get("results")
    if not results:
        st.info("Run a scenario to see results.")
        return

    em = results.get("Emissions", {})
    rz = results.get("outage_optimized_stats", {})

    c1, c2, c3 = st.columns(3)
    c1.metric("Annual CO₂e (t)", f"{em.get('annual_tons_co2', 0):,.0f}")
    c2.metric("Δ CO₂e vs BAU (t)", f"{em.get('annual_co2_change_tons', 0):,.0f}")
    c3.metric("Hours Critical Load Met", f"{rz.get('outage_durations_critical_load_met', 0)}")

    if not em and not rz:
        st.info("Backend needs to populate emissions/resilience fields to fully enable this card.")
