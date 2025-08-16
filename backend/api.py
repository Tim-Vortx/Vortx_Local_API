import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# Configuration via environment variables
PROJECT_ROOT = Path(os.getenv("REOPT_PROJECT_ROOT", Path(__file__).resolve().parents[1]))
RUNS_DIR = Path(os.getenv("REOPT_RUNS_DIR", Path(__file__).parent / "runs"))
DEFAULT_SOLVER = os.getenv("REOPT_SOLVER", "HiGHS")

RUNS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="REopt Runner")


class Scenario(BaseModel):
    """Minimal validation for REopt scenarios."""

    Site: dict
    ElectricLoad: dict
    ElectricTariff: dict


async def _run_julia(run_id: str, scenario_file: Path, result_file: Path, solver: str) -> None:
    """Execute the Julia model and persist results."""
    status_path = RUNS_DIR / run_id / "status.json"
    stdout_path = RUNS_DIR / run_id / "stdout.log"
    stderr_path = RUNS_DIR / run_id / "stderr.log"

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
    stdout, stderr = await proc.communicate()

    RUNS_DIR.joinpath(run_id).mkdir(parents=True, exist_ok=True)
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)

    if proc.returncode != 0:
        status = {"status": "error", "returncode": proc.returncode}
        if stderr:
            status["error"] = stderr.decode(errors="ignore")
        status_path.write_text(json.dumps(status))
        return

    try:
        data = json.loads(result_file.read_text())
        status = {"status": "completed"}
        status_path.write_text(json.dumps(status))
    except Exception as exc:  # pragma: no cover - defensive
        status = {"status": "error", "error": str(exc)}
        status_path.write_text(json.dumps(status))


@app.post("/reopt/run")
async def run_reopt(scenario: Scenario, solver: Optional[str] = Query(None)):
    """Kick off a REopt run and return a run identifier."""
    run_id = str(uuid.uuid4())
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    scenario_file = run_dir / "scenario.json"
    result_file = run_dir / "result.json"
    scenario_file.write_text(scenario.json())
    (run_dir / "status.json").write_text(json.dumps({"status": "running"}))

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
