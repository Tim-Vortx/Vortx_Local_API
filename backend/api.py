import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Body
from pydantic import BaseModel
import copy

# --- optional CORS so Streamlit/frontend can call this API ---
from fastapi.middleware.cors import CORSMiddleware

# Configuration via environment variables
PROJECT_ROOT = Path(os.getenv("REOPT_PROJECT_ROOT", Path(__file__).resolve().parents[1]))
RUNS_DIR = Path(os.getenv("REOPT_RUNS_DIR", Path(__file__).parent / "runs"))
DEFAULT_SOLVER = os.getenv("REOPT_SOLVER", "HiGHS")

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


def _normalize_scenario(scn: dict) -> dict:
    """Normalize common shorthand fields from clients into the shapes
    expected by the Julia/REopt constructors.

    - map ElectricLoad.hourly_profile -> ElectricLoad.loads_kw
    - ensure ElectricLoad.year and time_steps_per_hour exist (prefer Settings.tph if present)
    - force operating_reserve_required_fraction to 0.0 for on-grid scenarios
    - map simple tariff keys (energy_charge -> blended_annual_energy_rate, name -> urdb_label)
    """
    s = copy.deepcopy(scn)

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

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    print(f"[DEBUG] Julia process started for run_id={run_id}")

    async def _stream(stream, path: Path, label: str) -> str:
        lines: list[str] = []
        with path.open("wb") as f:
            while True:
                line = await stream.readline()
                if not line:
                    break
                f.write(line)
                f.flush()
                text = line.decode(errors="ignore")
                lines.append(text)
                print(f"[{label}] {text.rstrip()}")
        return "".join(lines)

    stdout_task = asyncio.create_task(_stream(proc.stdout, stdout_path, "STDOUT"))
    stderr_task = asyncio.create_task(_stream(proc.stderr, stderr_path, "STDERR"))
    returncode = await proc.wait()
    await stdout_task
    stderr_text = await stderr_task
    print(f"[DEBUG] Julia process finished for run_id={run_id} with returncode={returncode}")

    RUNS_DIR.joinpath(run_id).mkdir(parents=True, exist_ok=True)
    print(f"[DEBUG] Wrote stdout and stderr for run_id={run_id}")

    # Even if returncode == 0, check stderr for fatal keywords (MethodError/ERROR)
    if returncode != 0 or (stderr_text and ("MethodError" in stderr_text or "ERROR" in stderr_text)):
        print(f"[DEBUG] Julia process error for run_id={run_id}: returncode={returncode}")
        status = {"status": "error", "returncode": returncode}
        if stderr_text:
            status["error"] = stderr_text
        status_path.write_text(json.dumps(status))
        return

    try:
        # Ensure result.json exists; otherwise status will be error below
        data = json.loads(result_file.read_text())
        status = {"status": "completed"}
        status_path.write_text(json.dumps(status))
        print(f"[DEBUG] Run completed for run_id={run_id}")
    except Exception as exc:  # pragma: no cover - defensive
        status = {"status": "error", "error": str(exc)}
        status_path.write_text(json.dumps(status))
        print(f"[DEBUG] Exception in _run_julia for run_id={run_id}: {exc}")


@app.post("/reopt/run")
async def run_reopt(scenario: Scenario, solver: Optional[str] = Query(None)):
    """Kick off a REopt run and return a run identifier."""
    run_id = str(uuid.uuid4())
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    scenario_file = run_dir / "scenario.json"
    result_file = run_dir / "result.json"
    # Normalize and log the scenario received from the client
    try:
        raw = json.loads(scenario.json())
    except Exception:
        raw = json.loads(scenario.json())

    normalized = _normalize_scenario(raw)
    scenario_json_str = json.dumps(normalized, indent=2)
    print(f"[DEBUG] Received (normalized) scenario for run_id={run_id}: {scenario_json_str}")
    scenario_file.write_text(scenario_json_str)
    (run_dir / "status.json").write_text(json.dumps({"status": "running"}))

    print(f"[DEBUG] Starting background Julia task for run_id={run_id}")
    asyncio.create_task(
        _run_julia(run_id, scenario_file, result_file, solver or DEFAULT_SOLVER)
    )

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
    Replace this stub with a real REopt v3 schema if you have one handy.
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
    except Exception:
        normalized = scenario  # best-effort pass-through

    try:
        run_id = str(uuid.uuid4())
        run_dir = RUNS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        scenario_file = run_dir / "scenario.json"
        result_file = run_dir / "result.json"

        scenario_json_str = json.dumps(normalized, indent=2)
        print(f"[DEBUG] Received (normalized) scenario for run_id={run_id}: {scenario_json_str}")
        scenario_file.write_text(scenario_json_str)
        (run_dir / "status.json").write_text(json.dumps({"status": "running"}))

        print(f"[DEBUG] Starting background Julia task for run_id={run_id}")
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

    if isinstance(results, dict):
        results["status"] = "completed"
        return results
    else:
        return {"status": "completed", "result": results}
