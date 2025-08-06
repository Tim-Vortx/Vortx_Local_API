import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from werkzeug.exceptions import BadRequest
import time
import re

# Track temporary cooldowns for run_uuids after hitting rate limits
cooldowns = {}

API_URL = "https://developer.nrel.gov/api/reopt/v3/"

def _extract_support_id(body: str) -> str | None:
    match = re.search(r"support ID is: (\d+)", body, re.IGNORECASE)
    return match.group(1) if match else None

app = Flask(__name__)
CORS(app)  # allow React dev-server to call us

@app.route("/submit", methods=["POST"])
def submit():
    """Validate and forward a scenario to NREL's API."""
    if not request.is_json:
        logging.error("Request body is not JSON")
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        scenario = request.get_json()
        logging.info(f"Received scenario for submission: {scenario}")
    except BadRequest as e:
        logging.error(f"Malformed JSON in request: {e}")
        return jsonify({"error": "Malformed JSON in request"}), 400

    api_key = request.headers.get("X-Api-Key")
    logging.info(f"X-Api-Key header present: {api_key is not None}")
    if not api_key:
        return jsonify({"error": "Missing X-Api-Key header"}), 401

    post_url = f"{API_URL}job/"
    try:
        headers = {
            "User-Agent":   "VortxOpt/1.0",
            "Accept":       "application/json",
            "Content-Type": "application/json",
            "X-Api-Key":    api_key,
        }
        resp = requests.post(post_url, json=scenario, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        logging.info(f"Submit response from NREL: {data}")
    except requests.exceptions.HTTPError as e:
        if resp.status_code == 400:
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

    return jsonify({"run_uuid": run_uuid})


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

    api_key = request.headers.get("X-Api-Key")
    logging.info(f"X-Api-Key header present: {api_key is not None}")
    if not api_key:
        return jsonify({"error": "Missing X-Api-Key header"}), 401

    results_url = f"{API_URL}job/{run_uuid}/results/"
    logging.info(f"Polling status for run_uuid: {run_uuid}")
    logging.info(f"Requesting results from {results_url}")

    try:
        headers = {
            "User-Agent":   "VortxOpt/1.0",
            "Accept":       "application/json",
            "X-Api-Key":    api_key,
        }
        resp = requests.get(results_url, headers=headers)
        logging.info(f"/results response status {resp.status_code} for run_uuid {run_uuid}")
        if resp.status_code != 200:
            logging.warning(f"/results response body: {resp.text}")
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as e:
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "60"))
            cooldowns[run_uuid] = time.time() + retry_after
            logging.warning(f"NREL API rate limit hit for run_uuid {run_uuid}, retry after {retry_after}s")
            return (
                jsonify({"error": "Too Many Requests", "retry_after": retry_after}),
                429,
                {"Retry-After": str(retry_after)},
            )
        if resp.status_code == 400:
            error_detail = resp.text
            logging.error(f"NREL API 400 Bad Request from /results: {error_detail}")
            return jsonify({"error": "Bad Request from NREL API", "details": error_detail}), 400
        logging.error(
            "HTTP error from NREL API on results: %s; status=%s body=%s",
            e,
            getattr(resp, "status_code", "N/A"),
            getattr(resp, "text", ""),
        )
        return jsonify({"error": str(e)}), 502
    except requests.exceptions.RequestException as e:
        logging.error(f"Request exception from NREL API on results: {e}")
        return jsonify({"error": str(e)}), 502
    except ValueError as e:
        logging.error(f"Invalid JSON received from NREL API on results: {e}")
        return jsonify({"error": "Invalid JSON received from NREL API"}), 502

    status_val = data.get("status")

    # Detect failure or error statuses
    if status_val in ["Failed", "Error", "Cancelled"]:
        error_message = data.get("message", f"Job failed with status: {status_val}")
        logging.error(f"NREL job {run_uuid} failed: {error_message}")
        return jsonify({"error": error_message, "status": status_val}), 200

    if status_val.lower() in ["completed", "optimal"]:
        outputs = data.get("outputs")
        if outputs is None:
            logging.error(f"NREL API indicated completion but no outputs were returned for run_uuid {run_uuid}")
            return (
                jsonify({"error": "Outputs missing from NREL response", "status": status_val}),
                502,
            )
        data["outputs"] = outputs

    return jsonify(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
