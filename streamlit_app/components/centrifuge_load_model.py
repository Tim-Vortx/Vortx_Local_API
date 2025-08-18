"""Streamlit UI for the centrifuge load model.

This component exposes a simple interface for configuring a
``CentrifugeParams`` object, running the load model, and downloading the
results.  Parameters and results are persisted in ``st.session_state`` to
allow seamless interaction across reruns.
"""

from __future__ import annotations

import json
import io
from dataclasses import asdict

import streamlit as st

from streamlit_app.utils.centrifuge_load_model import (
    CentrifugeParams,
    build_centrifuge_load_curve,
)


_PARAMS_KEY = "centrifuge_params"
_RESULTS_KEY = "centrifuge_results"


def _get_params() -> CentrifugeParams:
    if _PARAMS_KEY not in st.session_state:
        st.session_state[_PARAMS_KEY] = CentrifugeParams()
    return st.session_state[_PARAMS_KEY]


def _get_results():
    return st.session_state.get(_RESULTS_KEY)


def show() -> None:
    """Render the centrifuge load model UI."""

    st.subheader("🌀 Centrifuge Load Model")
    params = _get_params()

    # --- JSON import/export controls ---
    c1, c2 = st.columns(2)
    with c1:
        uploaded = st.file_uploader("Import Params JSON", type="json", key="centrifuge_params_upload")
        if uploaded is not None:
            try:
                raw = json.load(uploaded)
                st.session_state[_PARAMS_KEY] = CentrifugeParams(**{**asdict(CentrifugeParams()), **raw})
                params = _get_params()
                st.success("Parameters loaded.")
            except Exception as exc:  # pragma: no cover - defensive
                st.error(f"Failed to parse JSON: {exc}")
    with c2:
        st.download_button(
            "Export Params JSON",
            data=json.dumps(asdict(params), indent=2),
            file_name="centrifuge_params.json",
            mime="application/json",
        )

    # --- Parameter tabs ---
    tab_pp, tab_elec, tab_ops, tab_run = st.tabs(
        ["Plant & Process", "Electrical & HVAC", "Spin-up & Ops", "Run & Results"]
    )

    with tab_pp:
        params.plant_swu_per_year = st.number_input(
            "Plant SWU/year", value=float(params.plant_swu_per_year), min_value=0.0
        )
        params.kwh_per_swu = st.number_input(
            "kWh per SWU", value=float(params.kwh_per_swu), min_value=0.0
        )
        params.interpret_kwh_per_swu_as_total_plant = st.checkbox(
            "Interpret kWh/SWU as total plant",
            value=params.interpret_kwh_per_swu_as_total_plant,
        )
        params.machine_swu_per_year = st.number_input(
            "SWU per machine per year",
            value=float(params.machine_swu_per_year),
            min_value=0.0,
        )
        params.availability = st.number_input(
            "Availability (0-1)", value=float(params.availability), min_value=0.0, max_value=1.0, step=0.01
        )
        params.num_cascades = st.number_input(
            "Number of cascades", value=int(params.num_cascades), min_value=1, step=1
        )
        params.year = st.number_input("Year", value=int(params.year), step=1)

    with tab_elec:
        params.hvac_fraction_of_running = st.number_input(
            "HVAC fraction of running load",
            value=float(params.hvac_fraction_of_running),
            min_value=0.0,
            step=0.01,
        )
        params.hvac_seasonal_amplitude = st.number_input(
            "HVAC seasonal amplitude",
            value=float(params.hvac_seasonal_amplitude),
            min_value=0.0,
            step=0.01,
        )
        params.season_peak_month = st.number_input(
            "Season peak month", value=int(params.season_peak_month), min_value=1, max_value=12, step=1
        )
        params.aux_kw_constant = st.number_input(
            "Auxiliary constant kW", value=float(params.aux_kw_constant), min_value=0.0
        )
        params.ride_through_seconds = st.number_input(
            "Ride-through seconds", value=float(params.ride_through_seconds), min_value=0.0
        )
        params.critical_fraction = st.number_input(
            "Critical load fraction",
            value=float(params.critical_fraction),
            min_value=0.0,
            max_value=1.0,
            step=0.01,
        )

    with tab_ops:
        params.daily_restart_fraction = st.number_input(
            "Daily restart fraction",
            value=float(params.daily_restart_fraction),
            min_value=0.0,
            max_value=1.0,
            step=0.001,
            format="%.3f",
        )
        params.spinup_minutes = st.number_input(
            "Spin-up minutes", value=float(params.spinup_minutes), min_value=0.0
        )
        params.spinup_power_factor = st.number_input(
            "Spin-up power factor", value=float(params.spinup_power_factor), min_value=0.0
        )
        start, end = params.spinup_window_hours
        start_end = st.slider(
            "Spin-up window hours",
            min_value=0,
            max_value=24,
            value=(int(start), int(end)),
        )
        params.spinup_window_hours = (start_end[0], start_end[1])
        params.random_seed = st.number_input("Random seed", value=int(params.random_seed), step=1)

    with tab_run:
        if st.button("Run model", key="centrifuge_run"):
            with st.spinner("Building load curve..."):
                df, summary = build_centrifuge_load_curve(params)
                st.session_state[_RESULTS_KEY] = {"df": df, "summary": summary}
        res = _get_results()
        if res:
            df = res["df"]
            summary = res["summary"]
            st.success("Model run complete.")
            st.line_chart(df["total_kw"], height=200)
            st.json(summary)

            csv_buf = io.StringIO()
            df.to_csv(csv_buf)
            st.download_button(
                "Download CSV", data=csv_buf.getvalue(), file_name="centrifuge_load_curve.csv", mime="text/csv"
            )
            reopt_payload = {
                "ElectricLoad": {
                    "loads_kw": [float(x) for x in df["total_kw"].round(3)],
                    "year": int(params.year),
                }
            }
            st.download_button(
                "Download REopt JSON",
                data=json.dumps(reopt_payload, indent=2),
                file_name="centrifuge_reopt_payload.json",
                mime="application/json",
            )

    st.session_state[_PARAMS_KEY] = params

