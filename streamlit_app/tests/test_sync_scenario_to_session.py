import sys
from pathlib import Path

import streamlit as st

# Ensure repo root and streamlit_app are on sys.path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
if str(ROOT / "streamlit_app") not in sys.path:
    sys.path.append(str(ROOT / "streamlit_app"))

from streamlit_app.app import _sync_scenario_to_session


def test_off_grid_flag_sets_selection():
    st.session_state.clear()
    st.session_state["scenario"] = {"Settings": {"off_grid_flag": True}}
    _sync_scenario_to_session()
    assert st.session_state["grid_connection"] == "Off-Grid"
