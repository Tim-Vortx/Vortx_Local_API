import streamlit as st
import json
from ..utils.backend_client import submit_scenario, get_status
from ..utils.validators import build_reopt_scenario, preflight_checks

def show():
    st.header("🚀 Run Optimization")

    # Build scenario from inputs in session_state
    scenario, errors = build_reopt_scenario(dict(st.session_state))
    # run quick client-side preflight checks on the built scenario (respects ZIP/lat parsing)
    preflight_errors = preflight_checks(scenario)
    # If the nested scenario in session_state contains loads_kw, show a short confirmation
    nested = st.session_state.get("scenario", {}) if isinstance(st.session_state.get("scenario"), dict) else {}
    el_nested = nested.get("ElectricLoad", {}) if isinstance(nested.get("ElectricLoad"), dict) else {}
    if "loads_kw" in el_nested:
        loads = el_nested.get("loads_kw")
        if loads is None:
            loads = []
        try:
            tph = int(nested.get("Settings", {}).get("time_steps_per_hour", 1))
        except Exception:
            tph = 1

        st.success(f"Loaded time series present: {len(loads)} points (will be submitted as ElectricLoad.loads_kw)")
        # show a single-day preview (first 24*tph steps)
        steps_per_day = 24 * int(tph)
        if len(loads) >= steps_per_day:
            sample = loads[:steps_per_day]
            # create a simple chart-friendly dict
            import pandas as pd
            times = [f"{int(i/tph):02d}:00" for i in range(steps_per_day)]
            df = pd.DataFrame({"kW": sample}, index=times)
            st.markdown("**Preview: first day's load**")
            st.line_chart(df)
        else:
            st.write("Load series present but too short to preview a full day.")
    with st.expander("Preview REopt Scenario JSON", expanded=False):
        st.code(json.dumps(scenario, indent=2))

    # show build-time validation errors
    if errors:
        for e in errors:
            st.error(e)

    # show preflight errors
    if preflight_errors:
        for e in preflight_errors:
            st.error(e)

    disable_run = bool(errors) or bool(preflight_errors)

    if st.button("Run REopt", disabled=disable_run):
        with st.status("Submitting job to REopt...", expanded=True) as status:
            try:
                job = submit_scenario(scenario)
                run_uuid = job.get("run_uuid")
                status.update(label=f"Submitted. run_uuid = {run_uuid}. Polling...")
                # simple one-shot poll; your backend may return full results directly
                results = get_status(run_uuid)
                st.session_state["results"] = results
                status.update(label="Complete", state="complete")
                st.success("Optimization finished.")
            except Exception as exc:
                status.update(label="Failed", state="error")
                st.exception(exc)
