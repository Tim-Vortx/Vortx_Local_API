# frontend/app.py
import os
import sys
import pathlib
import json

# Ensure repo root is on sys.path so `import streamlit_app.*` works when running
# `streamlit run streamlit_app/app.py` from the project root.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st

from streamlit_app.components import (
    project_location,
    load_builder,
    grid_tariff,
    ders,
    resilience,
    financials,
    run_panel,
    results_kpi,
    results_daily_ops,
    results_monthly,
    results_proforma,
    results_capex_opex,
    results_emissions_resilience,
    scenarios_compare,
)

# Optional: show which backend URL we're hitting
BACKEND_URL = os.getenv("VORTX_BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Vortx Microgrid Modeler", layout="wide")

# Initialize shared state once
if "scenario" not in st.session_state:
    st.session_state["scenario"] = {
        "Settings": {"time_steps_per_hour": 1, "off_grid_flag": False},
        "Site": {},
        "ElectricLoad": {},
        "ElectricTariff": {},
        "PV": {},
        "ElectricStorage": {},
        "Financial": {}
    }
if "results" not in st.session_state:
    st.session_state["results"] = None


def _sync_session_to_scenario():
    """Copy common top-level widget keys into the nested scenario so Run page always sees latest inputs."""
    sc = st.session_state.setdefault("scenario", {})
    sc.setdefault("Settings", {}).setdefault("time_steps_per_hour", 1)
    # Site
    site = sc.setdefault("Site", {})
    if "site_name" in st.session_state and st.session_state["site_name"]:
        site["name"] = st.session_state["site_name"]
    if "site_location" in st.session_state and st.session_state["site_location"]:
        site["site_location"] = st.session_state["site_location"]
    # Grid / tariff
    if "grid_connection" in st.session_state:
        sc.setdefault("Settings", {})["off_grid_flag"] = (st.session_state.get("grid_connection") == "Off-Grid")
    if "tariff_name" in st.session_state and st.session_state["tariff_name"]:
        sc.setdefault("ElectricTariff", {})["urdb_rate_name"] = st.session_state["tariff_name"]
    if "utility_name" in st.session_state and st.session_state["utility_name"]:
        sc.setdefault("ElectricTariff", {})["urdb_utility_name"] = st.session_state["utility_name"]
    # DERs
    if "pv_capacity_kw" in st.session_state and st.session_state["pv_capacity_kw"]:
        sc.setdefault("PV", {})["installed_capacity_kw"] = st.session_state["pv_capacity_kw"]
    if "bess_power_kw" in st.session_state or "bess_energy_kwh" in st.session_state:
        es = sc.setdefault("ElectricStorage", {})
        if "bess_power_kw" in st.session_state and st.session_state["bess_power_kw"]:
            es["installed_power_kw"] = st.session_state["bess_power_kw"]
        if "bess_energy_kwh" in st.session_state and st.session_state["bess_energy_kwh"]:
            es["installed_energy_kwh"] = st.session_state["bess_energy_kwh"]


def _sync_scenario_to_session():
    """Copy nested scenario values back to top-level widget keys so Inputs UI shows saved drafts."""
    # Only sync once per session to avoid overwriting user edits on reruns
    if st.session_state.get("_synced_from_scenario", False):
        return
    sc = st.session_state.get("scenario", {}) or {}
    # Site
    site = sc.get("Site", {}) or {}
    def _set_if_empty(key, value):
        if value is None:
            return
        existing = st.session_state.get(key)
        if existing is None or existing == "":  # Only overwrite when no existing value
            st.session_state[key] = value

    if "name" in site:
        _set_if_empty("site_name", site.get("name"))
    if "site_location" in site:
        _set_if_empty("site_location", site.get("site_location"))
    if "latitude" in site:
        _set_if_empty("latitude", site.get("latitude"))
    if "longitude" in site:
        _set_if_empty("longitude", site.get("longitude"))

    # Tariff
    tx = sc.get("ElectricTariff", {}) or {}
    if "urdb_utility_name" in tx:
        _set_if_empty("utility_name", tx.get("urdb_utility_name"))
    if "urdb_rate_name" in tx:
        _set_if_empty("tariff_name", tx.get("urdb_rate_name"))
    if "blended_annual_energy_rate" in tx:
        _set_if_empty("blended_er", tx.get("blended_annual_energy_rate"))
    if "blended_annual_demand_rate" in tx:
        _set_if_empty("blended_dr", tx.get("blended_annual_demand_rate"))

    # PV / Storage
    pv = sc.get("PV", {}) or {}
    if "installed_capacity_kw" in pv:
        _set_if_empty("pv_capacity_kw", pv.get("installed_capacity_kw"))
    es = sc.get("ElectricStorage", {}) or {}
    if "installed_power_kw" in es:
        _set_if_empty("bess_power_kw", es.get("installed_power_kw"))
    if "installed_energy_kwh" in es:
        _set_if_empty("bess_energy_kwh", es.get("installed_energy_kwh"))

    st.session_state["_synced_from_scenario"] = True


def log_session_state(stage):
    """Log the current state of st.session_state for debugging."""
    try:
        session_state_dict = {key: value for key, value in st.session_state.items()}
        with open("session_state_debug.log", "a") as log_file:
            log_file.write(f"\n[{stage}]\n")
            log_file.write(json.dumps(session_state_dict, indent=2))
    except Exception as e:
        print(f"Failed to log session state: {e}")


# Note: we call _sync_session_to_scenario after input widgets render (below) so
# it captures the latest user-entered values.

with st.sidebar:
    st.header("Navigation")
    section = st.selectbox("Section", ["Inputs", "Run", "Results", "Scenarios"])
    st.caption(f"Backend: `{BACKEND_URL}` (set VORTX_BACKEND_URL to change)")
    # Draft save/load removed; app now auto-saves inputs into the nested `scenario`.

# Route to pages
if section == "Inputs":
    # ensure top-level widgets reflect any nested scenario before rendering Inputs
    log_session_state("Before _sync_scenario_to_session")
    _sync_scenario_to_session()
    log_session_state("After _sync_scenario_to_session")
    with st.container(border=True):
        project_location.show()   # fills st.session_state["scenario"]["Site"] & Settings
    with st.container(border=True):
        load_builder.show()       # builds ElectricLoad (DOE or 8760)
    with st.container(border=True):
        grid_tariff.show()        # URDB/blended tariff + off-grid toggle
    with st.container(border=True):
        ders.show()               # PV, BESS, NG (CHP), Diesel
    with st.container(border=True):
        resilience.show()         # outage + critical load
    with st.container(border=True):
        financials.show()         # years, discount rate, ITC/MACRS, etc.

    # sync top-level widgets into the nested scenario after Inputs render
    log_session_state("Before _sync_session_to_scenario")
    _sync_session_to_scenario()
    log_session_state("After _sync_session_to_scenario")

elif section == "Run":
    with st.container(border=True):
        # ensure latest top-level inputs are copied into scenario before showing Run
        log_session_state("Before _sync_session_to_scenario")
        _sync_session_to_scenario()
        log_session_state("After _sync_session_to_scenario")
        run_panel.show()          # builds scenario JSON, POST /submit, poll /status

elif section == "Results":
    with st.container(border=True):
        results_kpi.show()
    with st.container(border=True):
        results_daily_ops.show()
    with st.container(border=True):
        results_monthly.show()
    with st.container(border=True):
        results_proforma.show()
    with st.container(border=True):
        results_capex_opex.show()
    with st.container(border=True):
        results_emissions_resilience.show()

elif section == "Scenarios":
    with st.container(border=True):
        scenarios_compare.show()
