import streamlit as st
from streamlit_app.utils.backend_client import get_urdb


def show():
    scn = st.session_state.setdefault("scenario", {})
    settings = scn.setdefault("Settings", {})
    et = scn.setdefault("ElectricTariff", {})

    st.subheader("⚡ Grid / Tariff & Off-grid")
    settings["off_grid_flag"] = st.checkbox("Off-grid (no utility interconnection)", value=settings.get("off_grid_flag", False), key="offgrid_toggle")
    if settings["off_grid_flag"]:
        et.clear()
        scn["Settings"]["off_grid_flag"] = True  # Explicitly set off_grid_flag to True
        scn["ElectricTariff"] = {}  # Clear ElectricTariff in the scenario JSON
        st.info("Off-grid selected. Tariff inputs are ignored.")
        return

    if st.button("Lookup URDB rates for site lat/lon", key="lookup_urdb"):
        lat = scn.get("Site", {}).get("latitude")
        lon = scn.get("Site", {}).get("longitude")
        try:
            st.session_state["_urdb_rates"] = get_urdb(lat, lon)
        except Exception as exc:
            st.error(f"Failed to fetch URDB rates: {exc}")

    rates = st.session_state.get("_urdb_rates", [])
    if rates:
        labels = [f"{r.get('label','<no label>')} — {r.get('utility','')}" for r in rates]
        idx = st.selectbox("Select a utility rate", options=range(len(labels)), format_func=lambda i: labels[i], key="urdb_idx")
        et.clear(); et["urdb_label"] = rates[idx]["label"]

    with st.expander("Or enter a simple blended tariff"):
        er = st.number_input("Blended energy rate ($/kWh)", value=et.get("blended_annual_energy_rate", 0.15), step=0.01, format="%.4f", key="blended_er")
        dr = st.number_input("Blended demand rate ($/kW-mo)", value=et.get("blended_annual_demand_rate", 10.0), step=1.0, format="%.2f", key="blended_dr")
        if st.button("Use blended tariff", key="use_blended"):
            et.clear()
            et["blended_annual_energy_rate"] = er
            et["blended_annual_demand_rate"] = dr
