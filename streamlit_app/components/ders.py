import streamlit as st


def show():
    st.header("🔋 DER Selection")

    st.subheader("Solar PV")
    st.checkbox("Include Solar PV", key="solar_enabled", value=st.session_state.get("solar_enabled", False))
    if st.session_state.get("solar_enabled", False):
        st.number_input("Capacity (kW)", min_value=0, value=st.session_state.get("pv_capacity_kw", 500), key="pv_capacity_kw")

    st.subheader("Battery Storage")
    st.checkbox("Include Battery", key="battery_enabled", value=st.session_state.get("battery_enabled", False))
    if st.session_state.get("battery_enabled", False):
        st.number_input("Power (kW)", min_value=0, value=st.session_state.get("bess_power_kw", 250), key="bess_power_kw")
        st.number_input("Energy (kWh)", min_value=0, value=st.session_state.get("bess_energy_kwh", 1000), key="bess_energy_kwh")

    st.subheader("Natural Gas Generator")
    st.checkbox("Include NG Gen", key="ng_enabled", value=st.session_state.get("ng_enabled", False))
    if st.session_state.get("ng_enabled", False):
        st.number_input("Capacity (kW)", min_value=0, value=st.session_state.get("ng_capacity_kw", 500), key="ng_capacity_kw")

    st.subheader("Diesel Generator")
    st.checkbox("Include Diesel Gen", key="diesel_enabled", value=st.session_state.get("diesel_enabled", False))
    if st.session_state.get("diesel_enabled", False):
        st.number_input("Capacity (kW)", min_value=0, value=st.session_state.get("diesel_capacity_kw", 500), key="diesel_capacity_kw")
