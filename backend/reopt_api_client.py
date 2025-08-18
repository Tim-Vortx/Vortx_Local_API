import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Body
from pydantic import BaseModel
import copy
from pathlib import Path as _Path

# --- optional CORS so Streamlit/frontend can call this API ---
from fastapi.middleware.cors import CORSMiddleware

# Configuration via environment variables
PROJECT_ROOT = Path(os.getenv("REOPT_PROJECT_ROOT", Path(__file__).resolve().parents[1]))
RUNS_DIR = Path(os.getenv("REOPT_RUNS_DIR", Path(__file__).parent / "runs"))
DEFAULT_SOLVER = os.getenv("REOPT_SOLVER", "HiGHS")

# Load a backend-local .env file if present. This allows operators to place
# a `backend/.env` file (repo-local) containing `REOPT_NREL_API_KEY=...` and
# have the FastAPI process load it at startup without changing system-wide
# environment files.
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    try:
        for raw in _env_path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            # only set if not already present in the environment
            os.environ.setdefault(k, v)
    except Exception:
        # don't fail startup if env file is malformed; log debug and continue
        print("[DEBUG] Failed to load backend/.env; continuing without it.")

RUNS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="REopt Runner")

# Allow all origins by default; tighten for production if you want
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # e.g., ["http://localhost:8501"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Scenario(BaseModel):
    """Minimal validation for REopt scenarios."""
    Site: dict
    ElectricLoad: dict
    ElectricTariff: dict
    Financial: dict = {
        "om_cost_escalation_rate_fraction": 0.025,
        "offtaker_tax_rate_fraction": 0.26,
        "third_party_ownership": False
    }


def _normalize_scenario(scn: dict) -> dict:
    """Normalize common shorthand fields from clients into the shapes
    expected by the Julia/REopt constructors.
    """
    s = copy.deepcopy(scn)

    # Validate Site.latitude and Site.longitude
    site = s.get("Site", {}) or {}
    lat = site.get("latitude")
    lon = site.get("longitude")
    if lat is None or lon is None:
        raise ValueError("Site.latitude and Site.longitude are required.")
    try:
        site["latitude"] = float(lat)
        site["longitude"] = float(lon)
    except ValueError:
        raise ValueError("Site.latitude and Site.longitude must be numeric.")
    s["Site"] = site

    # Ensure off_grid_flag and include_health_in_objective are in Settings
    settings = s.get("Settings", {}) or {}
    settings["off_grid_flag"] = bool(settings.get("off_grid_flag", False))
    settings["include_health_in_objective"] = bool(settings.get("include_health_in_objective", False))
    s["Settings"] = settings

    # Normalize Financial parameters
    financial = s.get("Financial", {}) or {}
    financial.setdefault("om_cost_escalation_rate_fraction", 0.025)
    financial.setdefault("offtaker_tax_rate_fraction", 0.26)
    financial.setdefault("third_party_ownership", False)

    # Extend Financial normalization to include all required parameters
    financial.setdefault("elec_cost_escalation_rate_fraction", 0.017)
    financial.setdefault("existing_boiler_fuel_cost_escalation_rate_fraction", 0.015)
    financial.setdefault("boiler_fuel_cost_escalation_rate_fraction", 0.015)
    financial.setdefault("chp_fuel_cost_escalation_rate_fraction", 0.015)
    financial.setdefault("generator_fuel_cost_escalation_rate_fraction", 0.012)
    financial.setdefault("owner_tax_rate_fraction", 0.26)
    financial.setdefault("owner_discount_rate_fraction", 0.0638)
    financial.setdefault("value_of_lost_load_per_kwh", 1.00)
    financial.setdefault("microgrid_upgrade_cost_fraction", 0.0)
    financial.setdefault("macrs_five_year", [0.2, 0.32, 0.192, 0.1152, 0.1152, 0.0576])
    financial.setdefault("macrs_seven_year", [0.1429, 0.2449, 0.1749, 0.1249, 0.0893, 0.0892, 0.0893, 0.0446])
    financial.setdefault("offgrid_other_capital_costs", 0.0)
    financial.setdefault("offgrid_other_annual_costs", 0.0)
    financial.setdefault("min_initial_capital_costs_before_incentives", None)
    financial.setdefault("max_initial_capital_costs_before_incentives", None)
    financial.setdefault("CO2_cost_per_tonne", 51.0)
    financial.setdefault("CO2_cost_escalation_rate_fraction", 0.042173)
    financial.setdefault("NOx_grid_cost_per_tonne", None)
    financial.setdefault("SO2_grid_cost_per_tonne", None)
    financial.setdefault("PM25_grid_cost_per_tonne", None)
    financial.setdefault("NOx_onsite_fuelburn_cost_per_tonne", None)
    financial.setdefault("SO2_onsite_fuelburn_cost_per_tonne", None)
    financial.setdefault("PM25_onsite_fuelburn_cost_per_tonne", None)
    financial.setdefault("NOx_cost_escalation_rate_fraction", None)
    financial.setdefault("SO2_cost_escalation_rate_fraction", None)
    financial.setdefault("PM25_cost_escalation_rate_fraction", None)
    financial.setdefault("include_health_in_objective", False)

    # Filter out unexpected keys in Financial
    allowed_financial_keys = {
        "om_cost_escalation_rate_fraction",
        "elec_cost_escalation_rate_fraction",
        "offtaker_discount_rate_fraction",
        "offtaker_tax_rate_fraction",
        "third_party_ownership",
        "bonus_depreciation_fraction",
        "capital_incentive",
        "analysis_years",
        "itc"
    }
    financial = {k: v for k, v in financial.items() if k in allowed_financial_keys}
    s["Financial"] = financial

    # Debugging: Log the final Financial section
    print(f"[DEBUG] Final Financial section: {financial}")

    # Remove invalid fields from Financial
    # Enhanced cleanup logic with debug logging
    invalid_financial_keys = {"latitude", "longitude", "off_grid_flag", "include_health_in_objective"}
    for key in invalid_financial_keys:
        if key in financial:
            print(f"[DEBUG] Removing invalid key from Financial: {key}")
            financial.pop(key)

    # Debugging: Log the final Financial section after removing invalid keys
    print(f"[DEBUG] Final Financial section after cleanup: {financial}")

    # Read Settings.time_steps_per_hour if present (backwards-safe)
    settings_tph = (s.get("Settings", {}) or {}).get("time_steps_per_hour", None)

    # ElectricLoad normalization
    el = s.get("ElectricLoad", {}) or {}
    # legacy/front-end field -> expected REopt field
    if "hourly_profile" in el and "loads_kw" not in el:
        el["loads_kw"] = el.pop("hourly_profile")

    # ensure time_steps_per_hour and year are present (prefer Settings.tph)
    el.setdefault("time_steps_per_hour", settings_tph or 1)
    # prefer ElectricLoad.year, then Site.year, then ElectricTariff.year, then 2017
    if "year" not in el:
        el["year"] = (
            s.get("Site", {}).get("year")
            or s.get("ElectricTariff", {}).get("year")
            or 2017
        )

    # operating reserve: must be 0.0 for on-grid scenarios
    # fallback to top-level Settings.off_grid_flag if ElectricLoad doesn't contain it
    off_grid = bool(
        el.get("off_grid_flag", False)
        or (s.get("Settings", {}) or {}).get("off_grid_flag", False)
    )
    if not off_grid:
        el["operating_reserve_required_fraction"] = 0.0
    else:
        el.setdefault("operating_reserve_required_fraction", 0.1)

    s["ElectricLoad"] = el

    # Validate loads_kw if present: must be iterable and have expected length
    if "loads_kw" in el:
        loads = el.get("loads_kw")
        try:
            # convert to list if not already; guard against None
            if loads is None:
                raise ValueError("ElectricLoad.loads_kw is None")
            if not isinstance(loads, (list, tuple)):
                loads = list(loads)
                el["loads_kw"] = loads
        except Exception:
            raise ValueError("ElectricLoad.loads_kw must be an array-like of numeric values")

        try:
            tph = int(el.get("time_steps_per_hour", 1))
        except Exception:
            tph = 1
        expected_len = 8760 * tph
        if len(loads) != expected_len:
            raise ValueError(
                f"ElectricLoad.loads_kw length {len(loads)} does not match expected {expected_len} (8760 * time_steps_per_hour)"
            )

    # ElectricTariff normalization
    tx = s.get("ElectricTariff", {}) or {}
    # Common shorthand: single energy charge -> blended annual energy rate
    if "energy_charge" in tx and "blended_annual_energy_rate" not in tx:
        ec = tx.get("energy_charge")
        if ec is not None:
            try:
                tx["blended_annual_energy_rate"] = float(ec)
            except Exception:
                # leave as-is if it can't be coerced
                pass

    # map friendly name to urdb_label if present
    if "name" in tx and "urdb_label" not in tx:
        tx.setdefault("urdb_label", tx.get("name", ""))

    # ensure tariff has the time_steps_per_hour and year keys so ElectricTariff() can use them
    tx.setdefault("time_steps_per_hour", el.get("time_steps_per_hour", 1))
    tx.setdefault("year", el.get("year", 2017))
    tx.setdefault("NEM", bool(tx.get("NEM", False)))

    # Only keep keys ElectricTariff constructor expects to avoid kwcall MethodError in Julia
    allowed_tx_keys = {
        "urdb_label",
        "urdb_response",
        "urdb_utility_name",
        "urdb_rate_name",
        "year",
        "time_steps_per_hour",
        "NEM",
        "wholesale_rate",
        "export_rate_beyond_net_metering_limit",
        "monthly_energy_rates",
        "monthly_demand_rates",
        "blended_annual_energy_rate",
        "blended_annual_demand_rate",
        "add_monthly_rates_to_urdb_rate",
        "tou_energy_rates_per_kwh",
        "add_tou_energy_rates_to_urdb_rate",
        "remove_tiers",
        "demand_lookback_months",
        "demand_lookback_percent",
        "demand_lookback_range",
        "coincident_peak_load_active_time_steps",
        "coincident_peak_load_charge_per_kw",
    }
    filtered_tx = {k: v for k, v in tx.items() if k in allowed_tx_keys}
    s["ElectricTariff"] = filtered_tx

    return s


async def _run_julia(run_id: str, scenario_file: Path, result_file: Path, solver: str) -> None:
    """Execute the Julia model and persist results."""
    status_path = RUNS_DIR / run_id / "status.json"
    stdout_path = RUNS_DIR / run_id / "stdout.log"
    stderr_path = RUNS_DIR / run_id / "stderr.log"
    print(f"[DEBUG] _run_julia started for run_id={run_id}")

    cmd = [
        "julia",
        str(PROJECT_ROOT / "scripts" / "run_reopt.jl"),
        str(scenario_file),
        str(result_file),
        solver,
    ]

    # Prepare environment for the Julia subprocess. Copy current env and
    # forward a backend-specific API key if provided. This lets operators
    # set REOPT_NREL_API_KEY in the backend environment and have Julia
    # pick it up as NREL_DEVELOPER_API_KEY.
    env = os.environ.copy()
    reopt_key = os.getenv("REOPT_NREL_API_KEY")
    if reopt_key:
        env["NREL_DEVELOPER_API_KEY"] = reopt_key

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    print(f"[DEBUG] Julia process started for run_id={run_id}")
    stdout, stderr = await proc.communicate()
    print(f"[DEBUG] Julia process finished for run_id={run_id} with returncode={proc.returncode}")

    RUNS_DIR.joinpath(run_id).mkdir(parents=True, exist_ok=True)
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    print(f"[DEBUG] Wrote stdout and stderr for run_id={run_id}")

    # Decode stdout/stderr for diagnostics
    stdout_text = stdout.decode(errors="ignore") if stdout else ""
    stderr_text = stderr.decode(errors="ignore") if stderr else ""

    # Treat non-zero return codes and MethodError as fatal. Avoid treating every
    # occurrence of the string "ERROR" in logs as a fatal condition because
    # some packages emit non-fatal ERROR-level messages during precompilation.
    fatal = proc.returncode != 0 or ("MethodError" in stderr_text)
    if fatal:
        print(f"[DEBUG] Julia process error for run_id={run_id}: returncode={proc.returncode}")
        status = {"status": "error", "returncode": proc.returncode}
        if stderr_text:
            status["error"] = stderr_text
        if stdout_text:
            status["stdout"] = stdout_text
        status_path.write_text(json.dumps(status))
        return

    try:
        # Ensure result.json exists and is valid JSON; otherwise mark as error
        data_text = result_file.read_text()
        data = json.loads(data_text)
        status = {"status": "completed"}
        status_path.write_text(json.dumps(status))
        print(f"[DEBUG] Run completed for run_id={run_id}")
    except Exception as exc:  # pragma: no cover - defensive
        status = {"status": "error", "error": str(exc)}
        # include captured stdout/stderr to help debug why parsing failed
        if stderr_text:
            status["stderr"] = stderr_text
        if stdout_text:
            # keep snippet to avoid extremely large status files
            status["stdout_snippet"] = stdout_text[:2000]
        status_path.write_text(json.dumps(status))
        print(f"[DEBUG] Exception in _run_julia for run_id={run_id}: {exc}")


@app.post("/reopt/run")
async def run_reopt(scenario: Scenario, solver: Optional[str] = Query(None)):
    """Run REopt with the provided scenario."""
    # Normalize the scenario
    normalized_scenario = _normalize_scenario(scenario.dict())

    # Log the normalized scenario for debugging
    print(f"[DEBUG] Normalized Scenario: {json.dumps(normalized_scenario, indent=2)}")

    # Generate a unique run ID
    run_id = str(uuid.uuid4())

    # Define file paths for the scenario and result
    scenario_file = RUNS_DIR / run_id / "scenario.json"
    result_file = RUNS_DIR / run_id / "result.json"

    # Create the run directory
    scenario_file.parent.mkdir(parents=True, exist_ok=True)

    # Write the normalized scenario to a file
    with scenario_file.open("w") as f:
        json.dump(normalized_scenario, f, indent=2)

    # Run the Julia script
    await _run_julia(run_id, scenario_file, result_file, solver or DEFAULT_SOLVER)

    return {"run_id": run_id}


@app.get("/reopt/result/{run_id}")
async def get_result(run_id: str):
    """Retrieve results or current status for a given run."""
    run_dir = RUNS_DIR / run_id
    status_path = run_dir / "status.json"
    if not status_path.exists():
        raise HTTPException(status_code=404, detail="run_id not found")

    status = json.loads(status_path.read_text())
    if status.get("status") != "completed":
        return status

    result_file = run_dir / "result.json"
    if not result_file.exists():  # pragma: no cover - defensive
        return {"status": "error", "error": "result missing"}

    result = json.loads(result_file.read_text())
    return {"status": "completed", "result": result}


# ============================================================
# Frontend compatibility endpoints (non-breaking wrappers)
# ============================================================

# Optional: schema endpoint for UI preflight (replace stub with real schema if desired)
@app.get("/schema")
async def schema():
    """
    Return a schema object for UI preflight.
    Replace this stub with a real REopt v3 job/inputs if you have one handy.
    """
    stub = {
        "ok": True,
        "note": "Stub schema endpoint. Replace with real REopt v3 job/inputs if desired."
    }
    return stub


# Optional: URDB lookup if you have a helper; otherwise return []
try:
    # Adjust import/function name to match your code if different
    from urdb_cache import find_rates as _find_urdb_rates  # type: ignore
except Exception:
    _find_urdb_rates = None

@app.get("/urdb")
async def urdb(lat: float = Query(...), lon: float = Query(...)):
    """
    Return a compact list of nearby tariffs for UI selection.
    Shape: [{"label":"<urdb_label>", "utility":"<utility>", "name":"<rate_name>"}]
    """
    if _find_urdb_rates is None:
        return []
    try:
        rates = _find_urdb_rates(lat, lon)
        out = []
        for r in rates:
            out.append({
                "label": r.get("label") or r.get("urdb_label") or "",
                "utility": r.get("utility") or r.get("utility_name") or "",
                "name": r.get("name") or r.get("rate_name") or "",
            })
        return out
    except Exception:
        return []


# POST /submit: accept a raw scenario dict, normalize, launch a run; return {"run_uuid": "..."}
@app.post("/submit")
async def submit(scenario: dict = Body(...)):
    """
    Frontend-friendly submit.
    Accepts a raw scenario dict (more permissive than the Pydantic Scenario),
    normalizes it using the same logic, and launches the Julia task.
    """
    try:
        normalized = _normalize_scenario(scenario)
    except ValueError as ve:
        # Reject invalid input rather than running Julia with bad inputs
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception:
        # Any other unexpected normalization error
        raise HTTPException(status_code=400, detail="bad scenario payload")

    try:
        run_id = str(uuid.uuid4())
        run_dir = RUNS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        scenario_file = run_dir / "scenario.json"
        result_file = run_dir / "result.json"

        scenario_file.write_text(json.dumps(normalized, indent=2))
        (run_dir / "status.json").write_text(json.dumps({"status": "running"}))

        asyncio.create_task(
            _run_julia(run_id, scenario_file, result_file, os.getenv("REOPT_SOLVER", DEFAULT_SOLVER))
        )

        return {"run_uuid": run_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"submit failed: {exc}")


# GET /status/{run_uuid}: return full results (flat), or interim status while running
@app.get("/status/{run_uuid}")
async def status(run_uuid: str):
    """
    Return the full results JSON with a top-level 'status' once complete.
    While running, returns whatever is in status.json (e.g., {"status":"running"}).
    """
    run_dir = RUNS_DIR / run_uuid
    status_path = run_dir / "status.json"
    if not status_path.exists():
        raise HTTPException(status_code=404, detail="run_uuid not found")

    status_data = json.loads(status_path.read_text())
    if status_data.get("status") != "completed":
        return status_data

    result_file = run_dir / "result.json"
    if not result_file.exists():
        return {"status": "error", "error": "result missing"}

    try:
        results = json.loads(result_file.read_text())
    except Exception as exc:
        return {"status": "error", "error": f"bad result json: {exc}"}

    # Always return a wrapper with explicit 'status' and 'result' keys so callers
    # can reliably unwrap a full results dict regardless of the internal shape.
    return {"status": "completed", "result": results}
