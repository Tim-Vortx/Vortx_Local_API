import os
import requests

BACKEND_URL = os.getenv("VORTX_BACKEND_URL", "http://localhost:8000")

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
