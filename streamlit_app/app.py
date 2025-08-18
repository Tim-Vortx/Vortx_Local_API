# frontend/app.py
import os
import streamlit as st
import sys
sys.path.append('/Users/tim_v/Coding/GeM/Vortx_Local_API')

# --- Sidebar / page setup ---
st.set_page_config(page_title="Vortx Microgrid Modeler", layout="wide")
BACKEND_URL = os.getenv("VORTX_BACKEND_URL", "http://localhost:8000")

# --- One-time state init (never reassign later) ---
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

# --- Import modular cards (each has a show() that mutates st.session_state) ---
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
    centrifuge_load_model,
)


def _sync_scenario_to_session() -> None:
    """Helper used by tests: copy a few stable values from the nested
    `st.session_state['scenario']` into legacy top-level widget keys so
    older components/tests that expect those keys still work.
    This must NOT reassign st.session_state['scenario'].
    """
    scn = st.session_state.get("scenario") or {}
    settings = scn.get("Settings", {}) or {}

    # Grid connection: Off-Grid vs Grid-Connected
    if settings.get("off_grid_flag"):
        st.session_state["grid_connection"] = "Off-Grid"
    else:
        st.session_state["grid_connection"] = "Grid-Connected"

# --- Sidebar nav ---
with st.sidebar:
    st.header("Navigation")
    section = st.radio("Section", ["Centrifuge Model", "Inputs", "Run", "Results", "Scenarios"], index=0)
    st.caption(f"Backend: `{BACKEND_URL}` (set VORTX_BACKEND_URL to change)")

# --- Page router ---
if section == "Inputs":
    with st.container(border=True):
        project_location.show()   # fills scenario["Site"], scenario["Settings"]
    with st.container(border=True):
        load_builder.show()       # fills scenario["ElectricLoad"] (DOE or 8760)
    with st.container(border=True):
        grid_tariff.show()        # fills scenario["ElectricTariff"] / Settings.off_grid_flag
    with st.container(border=True):
        ders.show()               # fills scenario["PV"], ["ElectricStorage"], and optional ["CHP"], ["Generator"]
    with st.container(border=True):
        resilience.show()         # fills outage & critical load
    with st.container(border=True):
        financials.show()         # fills scenario["Financial"]
        # Add missing financial parameters
        financial = st.session_state["scenario"].setdefault("Financial", {})
        financial["om_cost_escalation_rate_fraction"] = st.number_input(
            "O&M Cost Escalation Rate Fraction", value=0.025, min_value=0.0, max_value=1.0, step=0.001
        )
        financial["offtaker_tax_rate_fraction"] = st.number_input(
            "Offtaker Tax Rate Fraction", value=0.26, min_value=0.0, max_value=1.0, step=0.01
        )
        financial["third_party_ownership"] = st.checkbox(
            "Third Party Ownership", value=False
        )

elif section == "Run":
    with st.container(border=True):
        run_panel.show()          # builds scenario → POST /submit → poll /status → writes st.session_state["results"]

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

elif section == "Centrifuge Model":
    with st.container(border=True):
        centrifuge_load_model.show()

# Add a __main__ check to handle relative imports when executed directly
if __name__ == "__main__" and __package__ is None:
    import os
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

