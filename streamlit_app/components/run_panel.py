import streamlit as st
import json
import time
import os
from utils.backend_client import submit_scenario, get_status, get_result
from utils.validators import build_reopt_scenario, preflight_checks


def show():
    st.subheader("🚀 Run Optimization")

    # Build scenario using the validators helper (reads session_state['scenario'])
    scenario, errors = build_reopt_scenario(dict(st.session_state))
    preflight_errors = preflight_checks(scenario)

    nested = st.session_state.get("scenario", {}) if isinstance(st.session_state.get("scenario"), dict) else {}
    el_nested = nested.get("ElectricLoad", {}) if isinstance(nested.get("ElectricLoad"), dict) else {}
    if "loads_kw" in el_nested:
        loads = el_nested.get("loads_kw") or []
        try:
            tph = int(nested.get("Settings", {}).get("time_steps_per_hour", 1))
        except Exception:
            tph = 1
        st.success(f"Loaded time series present: {len(loads)} points (will be submitted as ElectricLoad.loads_kw)")
        steps_per_day = 24 * int(tph)
        if len(loads) >= steps_per_day:
            sample = loads[:steps_per_day]
            import pandas as pd
            times = [f"{int(i/tph):02d}:00" for i in range(steps_per_day)]
            df = pd.DataFrame({"kW": sample}, index=times)
            st.markdown("**Preview: first day's load**")
            st.line_chart(df)
        else:
            st.write("Load series present but too short to preview a full day.")

    with st.expander("Preview REopt Scenario JSON", expanded=False):
        st.code(json.dumps(scenario, indent=2))

    if errors:
        for e in errors:
            st.error(e)
    if preflight_errors:
        for e in preflight_errors:
            st.error(e)

    disable_run = bool(errors) or bool(preflight_errors)

    if st.button("Run REopt", disabled=disable_run, key="run_btn"):
        # Reset scenario in session state to ensure fresh submission
        st.session_state["scenario"] = None

        with st.status("Submitting & optimizing...", expanded=True) as status:
            try:
                job = submit_scenario(scenario)
                run_uuid = job.get("run_uuid")
                status.update(label=f"Submitted. run_uuid = {run_uuid}. Polling…")

                # Poll the backend until it reports completion (or failure) or we hit a timeout.
                timeout = int(os.getenv("VORTX_BACKEND_POLL_TIMEOUT", "600"))
                start = time.time()
                delay = 2.0
                max_delay = 10.0
                last_out = None
                while True:
                    try:
                        out = get_status(run_uuid)
                        last_out = out
                        print(f"[DEBUG] Backend response: {out}")  # Log backend response
                    except Exception as exc:
                        # Surface transient polling errors but keep retrying until timeout
                        status.update(label=f"Error polling backend: {exc}. Retrying…")
                        if time.time() - start > timeout:
                            status.update(label="Polling timed out")
                            st.warning(f"Polling timed out after {timeout} seconds; last error: {exc}")
                            st.session_state["results"] = {"error": str(exc)}
                            break
                        time.sleep(delay)
                        delay = min(max_delay, delay * 1.5)
                        continue

                    # Interpret backend status fields flexibly
                    status_field = None
                    for key in ("status", "state", "status_message", "result_status"):
                        if isinstance(out, dict) and key in out:
                            status_field = out.get(key)
                            break
                    status_text = (str(status_field) if status_field is not None else "unknown").lower()
                    status.update(label=f"run_uuid={run_uuid} — status: {status_text}")

                    if status_text in ("completed", "complete", "finished", "success"):
                        # The backend /status endpoint may return just a status dict
                        # or a wrapper containing the actual results. Try to normalize
                        # to a full results dict that UI components expect.
                        if isinstance(out, dict) and out.get("status") == "completed":
                            # If backend included 'result', unwrap it.
                            if "result" in out and isinstance(out.get("result"), dict):
                                st.session_state["results"] = out.get("result")
                            else:
                                # Fetch the detailed result from /reopt/result/<id>
                                try:
                                    detailed = get_result(run_uuid)
                                except Exception:
                                    # fallback: set whatever we have
                                    st.session_state["results"] = out
                                else:
                                    # If detailed has top-level 'result' unwrap, else accept as-is
                                    if isinstance(detailed, dict) and "result" in detailed and isinstance(detailed.get("result"), dict):
                                        st.session_state["results"] = detailed.get("result")
                                    else:
                                        st.session_state["results"] = detailed

                        else:
                            st.session_state["results"] = out

                        status.update(label="Complete", state="complete")
                        st.success("Optimization finished.")
                        break
                    if status_text in ("failed", "error"):
                        st.session_state["results"] = out
                        status.update(label="Failed", state="error")
                        st.error(f"Backend reported failure: {status_text}")
                        break

                    # timeout check
                    if time.time() - start > timeout:
                        status.update(label="Polling timed out")
                        st.warning(f"Polling timed out after {timeout} seconds. Last status: {status_text}")
                        st.session_state["results"] = out
                        break

                    # wait and retry with backoff
                    time.sleep(delay)
                    delay = min(max_delay, delay * 1.5)

            except Exception as exc:
                status.update(label="Failed", state="error")
                st.exception(exc)
