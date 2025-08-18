import os
import requests

BACKEND_URL = os.getenv("VORTX_BACKEND_URL", "http://localhost:8000")

# Configuration for calling the hosted NREL REopt API
NREL_API_BASE = os.getenv(
    "NREL_REOPT_API_BASE", "https://developer.nrel.gov/api/reopt/v3"
)
NREL_API_KEY = os.getenv("NREL_API_KEY") or os.getenv("NREL_DEVELOPER_API_KEY")

def get_schema():
    r = requests.get(f"{BACKEND_URL}/schema", timeout=30)
    r.raise_for_status()
    return r.json()

def get_urdb(lat: float, lon: float):
    r = requests.get(f"{BACKEND_URL}/urdb", params={"lat": lat, "lon": lon}, timeout=30)
    r.raise_for_status()
    return r.json()

def submit_scenario(payload: dict):
    r = requests.post(f"{BACKEND_URL}/submit", json=payload, timeout=60)
    # Provide a clearer message if the backend rejects the request
    if r.status_code == 403:
        raise RuntimeError(
            f"Backend returned 403 Forbidden for {BACKEND_URL}/submit.\n"
            "Verify the backend is running at this URL and that no proxy/auth is blocking the request.\n"
            f"Response: {r.text}"
        )
    if r.status_code == 422:
        # Unprocessable Entity: surface backend validation detail to the UI
        # FastAPI returns {'detail': 'message'} for HTTPException; include raw text for safety
        try:
            body = r.json()
            detail = body.get("detail") or body
        except Exception:
            detail = r.text
        raise RuntimeError(f"Validation error from backend: {detail}")

    r.raise_for_status()
    return r.json()

def get_status(run_uuid: str):
    r = requests.get(f"{BACKEND_URL}/status/{run_uuid}", timeout=60)
    r.raise_for_status()
    return r.json()


def get_result(run_uuid: str):
    """Fetch the detailed result for a run from the backend.

    The backend exposes `/reopt/result/{run_id}` which may return
    either a wrapper `{"status":"completed","result": {...}}` or
    the full results object with a `status` field injected. This helper
    returns whatever the backend provides and leaves normalization to the
    caller.
    """
    r = requests.get(f"{BACKEND_URL}/reopt/result/{run_uuid}", timeout=60)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# NREL-hosted REopt API helpers
# ---------------------------------------------------------------------------

def _nrel_payload(payload: dict) -> dict:
    """Wrap the scenario payload with API key for NREL-hosted runs."""
    if not NREL_API_KEY:
        raise RuntimeError("NREL_API_KEY environment variable not set")
    return {"api_key": NREL_API_KEY, "scenario": payload}


def submit_scenario_nrel(payload: dict):
    data = _nrel_payload(payload)
    r = requests.post(f"{NREL_API_BASE}/job", json=data, timeout=60)
    r.raise_for_status()
    return r.json()


def get_status_nrel(run_uuid: str):
    params = {"api_key": NREL_API_KEY}
    # Many REopt API versions expose /job/<id>/status
    r = requests.get(f"{NREL_API_BASE}/job/{run_uuid}/status", params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def get_result_nrel(run_uuid: str):
    params = {"api_key": NREL_API_KEY}
    # Final detailed results
    r = requests.get(f"{NREL_API_BASE}/job/{run_uuid}/results", params=params, timeout=60)
    r.raise_for_status()
    return r.json()
