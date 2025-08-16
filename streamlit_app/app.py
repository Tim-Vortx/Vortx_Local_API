import streamlit as st
import requests
import datetime
import json
import tempfile
from pathlib import Path
import os

repo_root = Path(__file__).resolve().parent.parent
scenarios_dir = repo_root / "test" / "scenarios"

st.title("REopt Model Runner (Streamlit)")

st.markdown("This app lets you pick a scenario JSON from the repo or upload one, run REopt (Julia) and view results.")


def render_results(results, container):
    """Render a structured view of the REopt results into the given Streamlit container."""
    if not results:
        container.info("No results to display")
        return

    # Top-level summary metrics (Financial)
    with container.expander("Summary / Key Metrics", expanded=True):
        if "Financial" in results and isinstance(results["Financial"], dict):
            fin = results["Financial"]
            # display a few likely useful metrics
            cols = container.columns(3)
            cols[0].metric("LCC", fin.get("lcc", "n/a"))
            cols[1].metric("Year 1 Energy Cost", fin.get("year_one_energy_cost_before_tax", "n/a"))
            cols[2].metric("Lifecycle Cost", fin.get("lifecycle_total_cost_after_tax", "n/a"))
        else:
            container.write("No financial summary available")

    # Electric tariff details
    with container.expander("Electric Tariff", expanded=False):
        et = results.get("ElectricTariff")
        if isinstance(et, dict):
            # show as key/value table
            rows = [[k, str(v)] for k, v in sorted(et.items())]
            container.table(rows)
        else:
            container.write("No ElectricTariff results")

    # Technologies (PV, Storage, Generator)
    with container.expander("Technology results", expanded=False):
        for tech in ("PV", "ElectricStorage", "Generator"):
            if tech in results:
                container.subheader(tech)
                t = results[tech]
                if isinstance(t, dict):
                    # show a compact list
                    for k, v in sorted(t.items()):
                        container.write(f"**{k}**: {v}")
                else:
                    container.write(t)

    # Time series / hourly results
    with container.expander("Time series / hourly data", expanded=False):
        # try a few common keys
        ts_keys = ["loads_kw", "loads_kwh", "ElectricLoad", "ElectricStorage"]
        found = False
        for k in (results.keys()):
            if isinstance(results.get(k), list) and len(results.get(k)) > 0:
                found = True
                sample = results.get(k)
                container.write(f"Found hourly array at key: {k} (len={len(sample)})")
                # show first 10 values
                container.write(sample[:24])
        if not found:
            container.write("No obvious hourly arrays found in results")

    # Full JSON viewer
    with container.expander("Full results JSON", expanded=False):
        container.json(results)


# list scenarios
scenario_files = []
if scenarios_dir.exists():
    scenario_files = sorted([p.relative_to(repo_root) for p in scenarios_dir.glob("*.json")])

choice = st.selectbox("Choose scenario (or upload)", ["(upload)"] + [str(p) for p in scenario_files])

uploaded = None
if choice == "(upload)":
    uploaded = st.file_uploader("Upload scenario JSON", type="json")

selected_path = None
if uploaded is not None:
    tmpdir = tempfile.mkdtemp()
    selected_path = Path(tmpdir) / "uploaded_scenario.json"
    with open(selected_path, "wb") as f:
        f.write(uploaded.getbuffer())
elif choice != "(upload)":
    selected_path = repo_root / choice

st.write("Selected:", selected_path)

# Tariff selector: extract ElectricTariff from available test scenarios
available_tariffs = {}
for p in scenario_files:
    try:
        ppath = repo_root / p
        with open(ppath) as f:
            d = json.load(f)
        if "ElectricTariff" in d:
            available_tariffs[str(p)] = d["ElectricTariff"]
    except Exception:
        pass

tariff_choice = None
if available_tariffs:
    tariff_keys = ["(keep from scenario)"] + list(available_tariffs.keys())
    tariff_choice = st.selectbox("Predefined tariff (optional)", tariff_keys)
    if tariff_choice and tariff_choice != "(keep from scenario)":
        chosen_tariff = available_tariffs.get(tariff_choice)
    else:
        chosen_tariff = None
else:
    chosen_tariff = None

# Asset toggles
st.markdown("### Assets to model")
with st.expander("Select assets"):
    use_pv = st.checkbox("PV", value=True)
    use_gen = st.checkbox("Generator", value=False)
    use_storage = st.checkbox("Electric Storage", value=True)

# Load generation helper
st.markdown("### Load profile options")
with st.expander("Generate or upload a load profile"):
    gen_type = st.selectbox("Generate synthetic load?", ["No", "Flat", "Diurnal"], index=0)
    gen_kwh = st.number_input("Annual kWh for synthetic load", value=100000.0)
    if st.button("Generate synthetic load"):
        # simple generation: flat hourly profile
        hours = 8760
        if gen_type == "Flat":
            vals = [gen_kwh / hours] * hours
        elif gen_type == "Diurnal":
            # simple diurnal shape
            base = gen_kwh / hours
            vals = [base * (0.5 + 0.5 * (1 + __import__("math").sin(2 * __import__("math").pi * (h % 24) / 24))) for h in range(hours)]
        else:
            vals = []
        if vals:
            # insert into edited JSON later via the editor controls
            st.session_state.setdefault("generated_load", vals)
            st.success(f"Generated {len(vals)}-hour profile")

if selected_path is not None:
    solver = st.selectbox("Solver", ["HiGHS", "GLPK"], index=0)
    run_button = st.button("Run REopt")

    status_container = st.empty()
    result_container = st.empty()

    if run_button:
        # Assemble scenario from selected file + UI inputs
        scenario_data = {}
        if selected_path.exists():
            try:
                with open(selected_path) as f:
                    scenario_data = json.load(f)
            except Exception as e:
                status_container.error(f"Failed to read selected scenario: {e}")
                scenario_data = {}

        # Apply chosen tariff if user picked one
        if chosen_tariff:
            scenario_data["ElectricTariff"] = chosen_tariff

        # Insert generated load if present (map to REopt expected key `loads_kw`)
        gen_load = st.session_state.get("generated_load")
        if gen_load:
            scenario_data.setdefault("Loads", {})["electric_load"] = gen_load
            el = scenario_data.setdefault("ElectricLoad", {})
            # REopt expects `loads_kw` (per timestep) and a `time_steps_per_hour` and `year` when providing raw loads
            el["loads_kw"] = gen_load
            el.setdefault("time_steps_per_hour", 1)
            el.setdefault("year", scenario_data.get("year", datetime.datetime.now().year))

        # Apply asset selections (add minimal placeholders or remove keys)
        if use_pv:
            scenario_data.setdefault("PV", {})
        else:
            scenario_data.pop("PV", None)

        if use_gen:
            scenario_data.setdefault("Generator", {})
        else:
            scenario_data.pop("Generator", None)

        if use_storage:
            scenario_data.setdefault("ElectricStorage", {})
        else:
            scenario_data.pop("ElectricStorage", None)

    # Auto-fill required minimal fields for validation
        if "year" not in scenario_data:
            scenario_data["year"] = datetime.datetime.now().year
        if "Site" not in scenario_data or not isinstance(scenario_data.get("Site"), dict):
            scenario_data["Site"] = {"name": "Site", "latitude": 35.0, "longitude": -106.0}
        if "ElectricLoad" not in scenario_data or not isinstance(scenario_data.get("ElectricLoad"), dict):
            scenario_data["ElectricLoad"] = {"doe_reference_name": "RetailStore", "annual_kwh": 1000.0}
        # Ensure required keys for raw loads
        el = scenario_data.setdefault("ElectricLoad", {})
        el.setdefault("time_steps_per_hour", 1)
        el.setdefault("year", scenario_data.get("year"))

        # operating_reserve_required_fraction applies only for off-grid scenarios
        off_grid = scenario_data.get("Settings", {}).get("off_grid_flag", False)
        el["operating_reserve_required_fraction"] = 0.1 if off_grid else 0.0
        if "ElectricTariff" not in scenario_data or not isinstance(scenario_data.get("ElectricTariff"), dict):
            scenario_data["ElectricTariff"] = {"urdb_label": "DefaultTariff", "name": "Default Tariff", "energy_charge": 0.12}

        # Preview assembled scenario
        st.markdown("### Scenario to be submitted")
        st.json(scenario_data)

        # Submit to backend
        api_url = "http://localhost:8000/reopt/run"
        try:
            with st.spinner("Submitting scenario to backend..."):
                resp = requests.post(api_url, json=scenario_data, params={"solver": solver})
            if resp.status_code != 200:
                status_container.error(f"Backend error: {resp.status_code}")
                try:
                    body = resp.json()
                    if isinstance(body, dict) and "detail" in body:
                        details = body["detail"]
                        if isinstance(details, list):
                            for d in details:
                                loc = d.get("loc") if isinstance(d, dict) else None
                                msg = d.get("msg") if isinstance(d, dict) else str(d)
                                status_container.error(f"Validation: {loc} - {msg}")
                        else:
                            status_container.json(body)
                    else:
                        status_container.json(body)
                except Exception:
                    status_container.text(resp.text)
            else:
                run_id = resp.json().get("run_id")
                status_container.info(f"Job submitted. Run ID: {run_id}")
                # Poll for results and show status updates
                result_url = f"http://localhost:8000/reopt/result/{run_id}"
                import time
                with st.spinner("Waiting for results from backend (this may take a while)..."):
                    for i in range(300):  # up to ~5 min
                        poll = requests.get(result_url)
                        if poll.status_code != 200:
                            status_container.error(f"Error polling for results: {poll.status_code}")
                            try:
                                status_container.text(poll.text)
                            except Exception:
                                pass
                            break
                        poll_json = poll.json()
                        # show current status
                        status_container.info(f"Status: {poll_json.get('status')}")
                        if poll_json.get("status") == "completed":
                            results = poll_json.get("result")
                            result_container.success("Model run complete — results loaded from backend.")
                            # show basic summary and full json
                            result_container.header("Summary")
                            if results and "Financial" in results:
                                fin = results["Financial"]
                                result_container.metric("LCC", fin.get("lcc", "n/a"))
                                result_container.metric("Year 1 Energy Cost", fin.get("year_one_energy_cost_before_tax", "n/a"))
                            # Render structured results
                            render_results(results, result_container)
                            break
                        elif poll_json.get("status") == "error":
                            status_container.error(f"Backend error: {poll_json.get('error')}")
                            break
                        time.sleep(1)
                    else:
                        status_container.error("Timeout waiting for results from backend.")
        except Exception as e:
            status_container.error(f"Exception communicating with backend: {e}")
