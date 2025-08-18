import streamlit as st


def show():
    scn = st.session_state.setdefault("scenario", {})
    el = scn.setdefault("ElectricLoad", {})
    st.subheader("🛡️ Resilience & Constraints")

    el["critical_load_fraction"] = st.number_input("Critical load fraction", value=el.get("critical_load_fraction", 1.0), min_value=0.0, max_value=1.0, step=0.1, key="crit_frac")
    c1, c2 = st.columns(2)
    with c1:
        start = st.number_input("Outage start hour (1..8760)", value=scn.get("ElectricUtility", {}).get("outage_start_time_step", 0), min_value=0, max_value=8760, step=1, key="out_start")
    with c2:
        end = st.number_input("Outage end hour (1..8760)", value=scn.get("ElectricUtility", {}).get("outage_end_time_step", 0), min_value=0, max_value=8760, step=1, key="out_end")
    if start and end:
        eu = scn.setdefault("ElectricUtility", {})
        eu["outage_start_time_step"] = int(start)
        eu["outage_end_time_step"] = int(end)
