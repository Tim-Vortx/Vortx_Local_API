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

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Track temporary cooldowns for run_uuids after hitting rate limits
cooldowns = {}

API_URL = "https://developer.nrel.gov/api/reopt/v3/"
NREL_API_KEY = os.getenv("NREL_API_KEY")

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

        # Basic input validation before logging and forwarding
        # Validate top-level blocks
        site = scenario.get("Site")
        el_load = scenario.get("ElectricLoad", {})
        loads_kw = el_load.get("loads_kw") if isinstance(el_load, dict) else None
        # Sanitize DOE reference name if provided by frontend but invalid for NREL
        if isinstance(el_load, dict) and "doe_reference_name" in el_load:
            removed = el_load.pop("doe_reference_name", None)
            logging.info(f"Removed ElectricLoad.doe_reference_name (was '{removed}') to satisfy NREL API constraints")

        if not site or not isinstance(site, dict) or \
           "latitude" not in site or "longitude" not in site:
            logging.error("Invalid or missing Site information: %s", site)
            return jsonify({"error": "Invalid or missing Site information"}), 400

        if not isinstance(loads_kw, list) or len(loads_kw) != 8760:
            logging.error("Invalid ElectricLoad.loads_kw: expected 8760 hourly values, got %s", 
                          type(loads_kw).__name__ if loads_kw is not None else loads_kw)
            return jsonify({"error": "ElectricLoad.loads_kw must contain exactly 8760 hourly values"}), 400

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
    except requests.exceptions.ConnectTimeout as e:
        logging.error(f"NREL API connect timed out on submit: {e}")
        return jsonify({"error": "NREL API connect timed out"}), 504
    except requests.exceptions.HTTPError as e:
        if getattr(resp, "status_code", None) == 400:
            error_detail = resp.text
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
        logging.warning("Failed to write scenario log file %s: %s", run_uuid_path, e)

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
    items = data.get("items", [])
    tariffs = [{"label": i.get("label"), "name": i.get("name")} for i in items]
    return jsonify(tariffs)


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

    start_time = time.time()
    data = None
    status_val = None
    # Poll for up to 5 minutes at 10-second intervals
    while True:
        try:
            resp = requests.get(results_url, headers=headers, timeout=DEFAULT_TIMEOUT)
            logging.info(f"/results response status {resp.status_code} for run_uuid {run_uuid}")

            if resp.status_code != 200:
                logging.warning("/results response body: %s", _redact_api_key(resp.text))
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "60"))
                    cooldowns[run_uuid] = time.time() + retry_after
                    logging.warning(f"NREL API rate limit hit for run_uuid {run_uuid}, retry after {retry_after}s")
                    # Sleep for retry_after seconds before retrying
                    time.sleep(retry_after)
                    if time.time() - start_time >= 300:
                        break
                    continue
                resp.raise_for_status()

            data = resp.json()

            # Determine status from possible fields
            status_val = None
            if isinstance(data, dict):
                status_val = data.get("status")
                if status_val is None and "outputs" in data:
                    try:
                        status_val = data["outputs"].get("Scenario", {}).get("status")
                    except Exception:
                        status_val = None

            # If status indicates completion, break
            if status_val and str(status_val).lower() not in ["optimizing...", "optimizing"]:
                break

            # Check max duration
            if time.time() - start_time >= 300:
                logging.info("Polling reached max duration of 300s; returning last response.")
                break

            time.sleep(10)
        except requests.exceptions.Timeout as e:
            logging.error(f"NREL API request timed out on results: {e}")
            return jsonify({"error": "NREL API request timed out"}), 504
        except requests.exceptions.ConnectTimeout as e:
            logging.error(f"NREL API connect timed out on results: {e}")
            return jsonify({"error": "NREL API connect timed out"}), 504
        except requests.exceptions.HTTPError as e:
            # Handle rate-limit here if available in the exception
            resp_status = getattr(e, "response", None)
            if resp_status is not None and getattr(resp_status, "status_code", None) == 429:
                retry_after = int(getattr(resp_status.headers, "get", lambda k, d: d)("Retry-After", "60"))
                cooldowns[run_uuid] = time.time() + retry_after
                logging.warning(f"NREL API rate limit hit for run_uuid {run_uuid}, retry after {retry_after}s")
                time.sleep(retry_after)
                if time.time() - start_time >= 300:
                    break
                continue
            logging.error(f"HTTP error from NREL API on results: {e}")
            return jsonify({"error": str(e)}), 502
        except requests.exceptions.RequestException as e:
            logging.error(f"Request exception from NREL API on results: {e}")
            return jsonify({"error": str(e)}), 502
        except ValueError as e:
            logging.error(f"Invalid JSON received from NREL API on results: {e}")
            return jsonify({"error": "Invalid JSON received from NREL API"}), 502

    if data is None:
        return jsonify({"error": "No response from NREL API"}), 502

    # If the API reports a terminal status, propagate it with outputs if present
    if status_val and str(status_val).lower() in ["failed", "error", "cancelled"]:
        error_message = data.get("message", f"Job failed with status: {status_val}")
        logging.error(f"NREL job {run_uuid} failed: {error_message}")
        return jsonify({"error": error_message, "status": status_val}), 200

    if status_val and str(status_val).lower() in ["completed", "optimal"]:
        outputs = data.get("outputs")
        if outputs is None:
            logging.error(f"NREL API indicated completion but no outputs were returned for run_uuid {run_uuid}")
            return jsonify({"error": "Outputs missing from NREL response", "status": status_val}), 502
        data["outputs"] = outputs

    return jsonify(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
