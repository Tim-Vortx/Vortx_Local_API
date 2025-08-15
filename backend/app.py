import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from werkzeug.exceptions import BadRequest
import time
import re
import json

from urdb_cache import fetch_tariffs

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=dotenv_path, override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Track temporary cooldowns for run_uuids after hitting rate limits
cooldowns = {}

API_URL = "https://developer.nrel.gov/api/reopt/stable/"
NREL_API_KEY = os.getenv("NREL_API_KEY")  # REopt API key
OPEN_EI_API_KEY = os.getenv("OPEN_EI_API_KEY", NREL_API_KEY)  # Allow separate key for OpenEI Utility Rates

def _extract_support_id(body: str) -> str | None:
    match = re.search(r"support ID is: (\\d+)", body, re.IGNORECASE)
    return match.group(1) if match else None


def _redact_api_key(data):
    """Remove the api_key field from dicts or JSON strings."""
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if k != "api_key"}
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
        except ValueError:
            text = re.sub(r'"api_key"\\s*:\\s*"[^"\\\\]*",\\s*', "", data)
            text = re.sub(r',\\s*"api_key"\\s*:\\s*"[^"\\\\]*"', "", text)
            text = re.sub(r'"api_key"\\s*:\\s*"[^"\\\\]*"', "", text)
            return text
        else:
            redacted = _redact_api_key(parsed)
            return json.dumps(redacted)
    return data

app = Flask(__name__)
CORS(app)  # allow React dev-server to call us

# Define a reasonable timeout to avoid hanging requests to NREL
DEFAULT_TIMEOUT = 600  # seconds

@app.route("/submit", methods=["POST"])
def submit():
    """Validate and forward a scenario to NREL's API."""
    if not request.is_json:
        logging.error("Request body is not JSON")
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        scenario = request.get_json()
        logging.info(f"Received scenario for submission: {scenario}")

        # If technologies include existing sizes without max bounds, fix them
        pv = scenario.get("PV")
        if isinstance(pv, dict) and "existing_kw" in pv and "max_kw" not in pv:
            pv["max_kw"] = pv["existing_kw"]
        batt = scenario.get("ElectricStorage")
        if isinstance(batt, dict):
            if "existing_kw" in batt and "max_kw" not in batt:
                batt["max_kw"] = batt["existing_kw"]
            if "existing_kwh" in batt and "max_kwh" not in batt:
                batt["max_kwh"] = batt["existing_kwh"]
        gen = scenario.get("Generator")
        if isinstance(gen, dict) and "existing_kw" in gen and "max_kw" not in gen:
            gen["max_kw"] = gen["existing_kw"]

        # Basic input validation before logging and forwarding
        site = scenario.get("Site")
        el_load = scenario.get("ElectricLoad", {})
        settings = scenario.get("Settings", {})
        loads_kw = el_load.get("loads_kw") if isinstance(el_load, dict) else None

        if not site or not isinstance(site, dict) or \
           "latitude" not in site or "longitude" not in site:
            logging.error("Invalid or missing Site information: %s", site)
            return jsonify({"error": "Invalid or missing Site information"}), 400

        if isinstance(loads_kw, list):
            tsp = settings.get("time_steps_per_hour", 1) or 1
            expected = 8760 * tsp
            if len(loads_kw) != expected:
                logging.error(
                    "Invalid ElectricLoad.loads_kw: expected %s values, got %s",
                    expected,
                    len(loads_kw),
                )
                return (
                    jsonify(
                        {
                            "error": (
                                "ElectricLoad.loads_kw must contain exactly "
                                f"{expected} values"
                            )
                        }
                    ),
                    400,
                )

            # Ensure year is provided for custom loads
            el_load.setdefault("year", settings.get("analysis_year", datetime.utcnow().year))
            if "doe_reference_name" in el_load:
                removed = el_load.pop("doe_reference_name")
                logging.info(
                    f"Removed ElectricLoad.doe_reference_name (was '{removed}') because custom loads were supplied"
                )

        et = scenario.get("ElectricTariff", {})
        if not isinstance(et, dict):
            return jsonify({"error": "ElectricTariff block required"}), 400
        has_urdb = "urdb_label" in et
        has_blended = any(k.startswith("blended") for k in et.keys())
        has_tou = any(k.startswith("tou") for k in et.keys())
        if sum([has_urdb, has_blended, has_tou]) != 1:
            logging.error(
                "ElectricTariff must include exactly one of urdb_label, blended rates, or TOU definitions"
            )
            return (
                jsonify(
                    {
                        "error": "ElectricTariff must include exactly one of urdb_label, blended rates, or TOU definitions"
                    }
                ),
                400,
            )

        # Ensure ElectricTariff block includes the selected tariff
        if "selected_tariff" in scenario:
            selected_tariff = scenario.pop("selected_tariff")
            scenario["ElectricTariff"] = {"urdb_label": selected_tariff.get("label")}

        # Translate natural gas generators to CHP objects
        for key in list(scenario.keys()):
            if not key.lower().startswith("generator"):
                continue
            gen = scenario[key]
            if not isinstance(gen, dict):
                continue
            fuel = gen.get("fuel_type", "").lower()
            if fuel in {"natural_gas", "natural gas", "ng"}:
                # Skip CHP conversion for off-grid scenarios
                if scenario.get("Settings", {}).get("off_grid_flag", False):
                    continue
                chp = gen.copy()
                if "fuel_cost_per_mmbtu" not in chp and "fuel_cost_per_gal" in chp:
                    chp["fuel_cost_per_mmbtu"] = chp.pop("fuel_cost_per_gal")
                scenario["CHP"] = chp
                scenario.pop(key)

        financial = scenario.setdefault("Financial", {})
        financial.setdefault("analysis_years", 25)
        financial.setdefault("escalation_pct", 0)
        financial.setdefault("om_cost_escalation_pct", 0)
        financial.setdefault("offtaker_discount_pct", 0)
        financial.setdefault("offtaker_tax_pct", 0)

        # Persist the latest scenario to disk for debugging/analysis
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        latest_path = os.path.join(log_dir, "latest_scenario.json")
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        timestamped_path = os.path.join(log_dir, f"scenario_{timestamp}.json")
        try:
            os.makedirs(log_dir, exist_ok=True)
            with open(latest_path, "w") as f:
                json.dump(scenario, f, indent=2)
            with open(timestamped_path, "w") as f:
                json.dump(scenario, f, indent=2)
        except OSError as e:
            logging.warning(
                "Failed to write scenario log files to %s: %s", log_dir, e
            )
    except BadRequest as e:
        logging.error(f"Malformed JSON in request: {e}")
        return jsonify({"error": "Malformed JSON in request"}), 400

    generator_keys = [k for k in scenario.keys() if k.lower().startswith("generator")]
    if generator_keys:
        logging.info(f"Forwarding generator keys to NREL: {generator_keys}")

    if not NREL_API_KEY:
        logging.error("NREL_API_KEY is not configured")
        return jsonify({"error": "Server missing NREL API key"}), 500

    post_url = f"{API_URL}job/"
    try:
        headers = {
            "User-Agent":   "VortxOpt/1.0",
            "Accept":       "application/json",
            "Content-Type": "application/json",
            "X-Api-Key":    NREL_API_KEY,
        }
        start_time = time.time()
        # Forward scenario without altering fuel-cost fields or units
        resp = requests.post(post_url, json=scenario, headers=headers, timeout=DEFAULT_TIMEOUT)
        duration = time.time() - start_time
        logging.info(f"NREL POST /job/ completed in {duration:.2f}s with status {resp.status_code}")
        resp.raise_for_status()
        data = resp.json()
        logging.info("Submit response from NREL: %s", _redact_api_key(data))
    except requests.exceptions.Timeout as e:
        logging.error(f"NREL API request timed out on submit: {e}")
        return jsonify({"error": "NREL API request timed out"}), 504
    except requests.exceptions.HTTPError as e:
        resp_obj = getattr(e, 'response', None)
        if resp_obj is not None and getattr(resp_obj, "status_code", None) == 400:
            error_detail = getattr(resp_obj, "text", str(e))
            logging.error(f"NREL API 400 Bad Request on submit: {error_detail}")
            return jsonify({"error": "Bad Request from NREL API", "details": error_detail}), 400
        logging.error(f"HTTP error from NREL API on submit: {e}")
        return jsonify({"error": str(e)}), 502
    except requests.exceptions.RequestException as e:
        logging.error(f"Request exception from NREL API on submit: {e}")
        return jsonify({"error": str(e)}), 502
    except ValueError as e:
        logging.error(f"Invalid JSON received from NREL API on submit: {e}")
        return jsonify({"error": "Invalid JSON received from NREL API"}), 502

    run_uuid = data.get("run_uuid")
    if not run_uuid:
        logging.error(f"NREL response missing run_uuid: {data}")
        return jsonify({"error": "run_uuid missing from NREL response"}), 502

    # Also store the scenario by run_uuid for historical record keeping
    try:
        run_uuid_path = os.path.join(log_dir, f"scenario_{run_uuid}.json")
        with open(run_uuid_path, "w") as f:
            json.dump(scenario, f, indent=2)
    except OSError as e:
        logging.warning("Failed to write scenario log file %s: %s", f"scenario_{run_uuid}.json", e)

    return jsonify({"run_uuid": run_uuid})


@app.route("/urdb", methods=["GET"])
def urdb():
    """Return cached URDB tariff options for a location."""
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is None or lon is None:
        return jsonify({"error": "lat and lon required"}), 400
    try:
        data = fetch_tariffs(lat, lon, api_key=NREL_API_KEY)
    except Exception as e:
        logging.error(f"URDB lookup failed for {lat},{lon}: {e}")
        return jsonify({"error": "URDB lookup failed"}), 502
    # Return full tariff item objects so the frontend can display detailed rate / TOU structures.
    # (Payload size is modest for typical item counts.)
    return jsonify(data.get("items", []))


@app.route("/urdb/<label>", methods=["GET"])
def urdb_detail(label):
    """Fetch a single URDB tariff by label (bypasses cache for full detail)."""
    if not OPEN_EI_API_KEY:
        logging.warning("OPEN_EI_API_KEY not set; attempting detail fetch without key (may return limited fields)")
    # Basic in-memory throttle: if same label requested >5 times in 10s window, short-circuit
    window_seconds = 10
    now = time.time()
    hits = app.config.setdefault('_URDB_DETAIL_HITS', {})
    # prune old
    for k, arr in list(hits.items()):
        hits[k] = [t for t in arr if now - t < window_seconds]
        if not hits[k]:
            hits.pop(k, None)
    arr = hits.setdefault(label, [])
    arr.append(now)
    if len(arr) > 5:
        logging.warning(f"Throttling excessive /urdb/{label} requests: {len(arr)} in {window_seconds}s")
        return jsonify({"error": "Too many requests for this label"}), 429
    # The OpenEI API supports getpage=<label> to retrieve a specific tariff page
    url = (
        "https://api.openei.org/utility_rates"
        f"?version=8&format=json&detail=full&getpage={label}" + (f"&api_key={OPEN_EI_API_KEY}" if OPEN_EI_API_KEY else "")
    )
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"URDB single tariff fetch failed for {label}: {e}")
        return jsonify({"error": "URDB single tariff fetch failed"}), 502
    items = data.get("items") or []
    # Log presence of structures for debugging
    if isinstance(items, list) and items:
        first = items[0]
        logging.info("/urdb/%s detail keys: %s", label, list(first.keys())[:25])
        logging.info("Rate structure present? energy=%s demand=%s", 'energyratestructure' in first, 'demandratestructure' in first)
    # items can sometimes be a dict for single responses; normalize to first item
    if isinstance(items, dict):
        return jsonify(items)
    if items:
        return jsonify(items[0])
    return jsonify({"error": "Tariff not found"}), 404


@app.route("/schema", methods=["GET"])
def schema():
    """Proxy the REopt input schema from NREL."""
    if not NREL_API_KEY:
        logging.error("NREL_API_KEY is not configured")
        return jsonify({"error": "Server missing NREL API key"}), 500
    url = "https://developer.nrel.gov/api/reopt/v3/job/inputs"
    try:
        resp = requests.get(url, params={"api_key": NREL_API_KEY}, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch schema from NREL: {e}")
        return jsonify({"error": "Failed to fetch schema"}), 502
    return jsonify(resp.json())


@app.route("/status/<run_uuid>", methods=["GET"])
def status(run_uuid):
    now = time.time()
    cooldown_until = cooldowns.get(run_uuid)
    if cooldown_until and now < cooldown_until:
        retry_after = int(cooldown_until - now)
        return (
            jsonify(
                {
                    "error": "Polling too frequently. Please retry later.",
                    "retry_after": retry_after,
                    "rate_limit_hit": True,
                }
            ),
            429,
            {"Retry-After": str(retry_after)},
        )

    if not NREL_API_KEY:
        logging.error("NREL_API_KEY is not configured")
        return jsonify({"error": "Server missing NREL API key"}), 500

    results_url = f"{API_URL}job/{run_uuid}/results/"
    logging.info(f"Polling status for run_uuid: {run_uuid}")
    logging.info(f"Requesting results from {results_url}")

    headers = {
        "User-Agent": "VortxOpt/1.0",
        "Accept": "application/json",
        "X-Api-Key": NREL_API_KEY,
    }

    try:
        resp = requests.get(results_url, headers=headers, timeout=DEFAULT_TIMEOUT)
        logging.info(
            f"/results response status {resp.status_code} for run_uuid {run_uuid}"
        )
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "60"))
            cooldowns[run_uuid] = time.time() + retry_after
            logging.warning(
                f"NREL API rate limit hit for run_uuid {run_uuid}, retry after {retry_after}s"
            )
            return (
                jsonify(
                    {
                        "error": "NREL API rate limit hit",
                        "retry_after": retry_after,
                        "rate_limit_hit": True,
                    }
                ),
                429,
                {"Retry-After": str(retry_after)},
            )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout as e:
        logging.error(f"NREL API request timed out on results: {e}")
        return jsonify({"error": "NREL API request timed out"}), 504
    except requests.exceptions.HTTPError as e:
        resp_status = getattr(e, "response", None)
        if resp_status is not None and getattr(resp_status, "status_code", None) == 400:
            error_detail = getattr(resp_status, "text", "")
            logging.error(
                f"NREL API 400 Bad Request on results for run_uuid {run_uuid}: {error_detail}"
            )
            return (
                jsonify({"error": "Bad Request from NREL API", "details": error_detail}),
                200,
            )
        logging.error(f"HTTP error from NREL API on results: {e}")
        return jsonify({"error": str(e)}), 502
    except requests.exceptions.RequestException as e:
        logging.error(f"Request exception from NREL API on results: {e}")
        return jsonify({"error": str(e)}), 502
    except ValueError as e:
        logging.error(f"Invalid JSON received from NREL API on results: {e}")
        return jsonify({"error": "Invalid JSON received from NREL API"}), 502

    # Determine status from possible fields
    status_val = None
    if isinstance(data, dict):
        status_val = data.get("status")
        if status_val is None and "outputs" in data:
            try:
                status_val = data["outputs"].get("Scenario", {}).get("status")
            except Exception:
                status_val = None

    # If the API reports a terminal status, propagate it with outputs if present
    if status_val and str(status_val).lower() in ["failed", "error", "cancelled"]:
        error_message = data.get("message", f"Job failed with status: {status_val}")
        logging.error(f"NREL job {run_uuid} failed: {error_message}")
        return jsonify({"error": error_message, "status": status_val}), 200

    if status_val and str(status_val).lower() in ["completed", "optimal"]:
        outputs = data.get("outputs")
        if outputs is None:
            logging.error(
                f"NREL API indicated completion but no outputs were returned for run_uuid {run_uuid}"
            )
            return jsonify({"error": "Outputs missing from NREL response", "status": status_val}), 502
        # Save full NREL output to logs/results_<run_uuid>.json
        results_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(results_dir, exist_ok=True)
        results_path = os.path.join(results_dir, f"results_{run_uuid}.json")
        try:
            with open(results_path, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logging.warning(
                "Failed to write NREL results file %s: %s", results_path, e
            )
        return jsonify({"status": status_val, "outputs": outputs, "rate_limit_hit": False})

    # Not finished yet; just return the current status
    return jsonify({"status": status_val or "optimizing", "rate_limit_hit": False})


# Simple alias for frontend which expects a /results/<run_uuid> endpoint.
# The current frontend fetches /results to get the full output object after
# the status polling has indicated completion. Originally only /status
# existed, so the fetch failed (404) and the power chart never received data.
# By reusing the status handler we ensure identical behavior without
# duplicating logic. Once the job is complete the first iteration of the
# status loop returns immediately.
@app.route("/results/<run_uuid>", methods=["GET"])
def results_route(run_uuid):
    return status(run_uuid)


# Helper to fetch OpenEI Utility Rates (version 3) for a given location
def _fetch_util_rates(lat: float, lon: float, api_key: str | None = None) -> dict:
    url = (
        "https://api.openei.org/utility_rates"
        f"?version=3&lat={lat}&lon={lon}"
    )
    if api_key:
        url += f"&api_key={api_key}"
    resp = requests.get(url, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


@app.route("/api/tariffs", methods=["GET"])
def api_tariffs():
    """Return normalized tariffs for a given location (lat, lon).
    Example: /api/tariffs?lat=34.05&lon=-118.25
    """
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is None or lon is None:
        return jsonify({"error": "lat and lon required"}), 400
    try:
        # Use the cached URDB fetch (version=8) to get the same items returned
        # by the /urdb endpoint; the v3 util_rates endpoint can return a
        # different set which caused some entries to be missing from the
        # /api/tariffs listing.
        data = fetch_tariffs(lat, lon, api_key=OPEN_EI_API_KEY)
        items = data.get("items", []) if isinstance(data, dict) else []
        tariffs = []
        for it in items:
            # Preserve a few raw OpenEI fields so the frontend can apply
            # richer filters (service_type, sectors, approved) without
            # re-querying OpenEI.
            tariffs.append({
                "id": str(it.get("label") or it.get("id") or ""),
                "label": it.get("label"),
                "name": it.get("name") or it.get("label") or "",
                "utility_name": it.get("utility_name") or it.get("utility") or "",
                "rate_type": it.get("rate_type") or it.get("ratestructure") or "",
                "service_type": it.get("service_type") or it.get("service") or None,
                "sectors": it.get("sectors") or it.get("sector") or None,
                "approved": it.get("approved") if "approved" in it else None,
                "is_approved": it.get("is_approved") if "is_approved" in it else None,
                "effective_from": it.get("effective_from") or it.get("from"),
                "effective_to": it.get("effective_to") or it.get("to"),
                "is_current": it.get("is_current", False),
                "monthly_fixed_charge": it.get("monthly_fixed_charge") or it.get("monthly_charge") or it.get("monthly_fee") or 0,
                "ratestructure": it.get("ratestructure", []),
                "energy_rates": it.get("energy_rates", []),
                "demand_rates": it.get("demand_rates", []),
                "notes": it.get("notes", ""),
                # Include the raw item for edge-case inspection in the UI/dev console
                "raw": it,
            })
        # Deduplicate by utility + name: prefer approved/current records and the most recent startdate/revision
        deduped = {}
        def score_item(x):
            # Returns tuple for comparison: higher is better
            approved = bool(x.get('approved') is True or x.get('is_approved') is True or x.get('is_current'))
            is_current = bool(x.get('is_current'))
            raw = x.get('raw') or {}
            start = 0
            try:
                start = int(raw.get('startdate') or raw.get('start') or 0)
            except Exception:
                start = 0
            revs = raw.get('revisions') or []
            maxrev = 0
            try:
                if isinstance(revs, list) and revs:
                    maxrev = max(int(r) for r in revs if isinstance(r, int) or (isinstance(r, str) and r.isdigit()))
            except Exception:
                maxrev = 0
            return (1 if approved else 0, 1 if is_current else 0, int(start), int(maxrev))

        for t in tariffs:
            key = (t.get('utility_name') or '').strip().lower() + '||' + (t.get('name') or '').strip().lower()
            if not key.strip('||'):
                # fallback to id if no name/utility
                key = 'id||' + (t.get('id') or '')
            existing = deduped.get(key)
            if not existing:
                deduped[key] = t
                continue
            if score_item(t) > score_item(existing):
                deduped[key] = t

        tariffs = list(deduped.values())
        return jsonify({"tariffs": tariffs})
    except requests.exceptions.RequestException as e:
        logging.error(f"Tariffs fetch failed for {lat},{lon}: {e}")
        return jsonify({"error": "Tariffs fetch failed"}), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
