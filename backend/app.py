import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

from flask import Flask, request, jsonify
from flask_cors import CORS
import os, requests
from dotenv import load_dotenv
from pathlib import Path
from werkzeug.exceptions import BadRequest

dotenv_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=dotenv_path, override=True)  # reads .env
API_KEY = os.getenv("NREL_API_KEY")
logging.info(f"NREL_API_KEY loaded: {API_KEY}")  # debug loaded key
if API_KEY is None:
    raise RuntimeError(
        "NREL_API_KEY is not set. Please define it in the environment or .env file."
    )

# Root endpoint matches NREL's post_and_poll.py conventions
API_URL = "https://developer.nrel.gov/api/reopt/v3"

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

    post_url = f"{API_URL}/job/?api_key={API_KEY}"
    try:
        resp = requests.post(post_url, json=scenario)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as e:
        if resp.status_code == 400:
            error_detail = resp.text
            logging.error(f"NREL API 400 Bad Request response: {error_detail}")
            return jsonify({"error": "Bad Request from NREL API", "details": error_detail}), 400
        logging.error(f"HTTP error from NREL API: {e}")
        return jsonify({"error": str(e)}), 502
    except requests.exceptions.RequestException as e:
        logging.error(f"Request exception from NREL API: {e}")
        return jsonify({"error": str(e)}), 502
    except ValueError as e:
        logging.error(f"Invalid JSON received from NREL API: {e}")
        return jsonify({"error": "Invalid JSON received from NREL API"}), 502

    run_uuid = data.get("run_uuid")
    if not run_uuid:
        logging.error(f"NREL response missing run_uuid: {data}")
        return jsonify({"error": "run_uuid missing from NREL response"}), 502

    return jsonify({"run_uuid": run_uuid})

@app.route("/status/<run_uuid>", methods=["GET"])
def status(run_uuid):

    import time
    results_url = f"{API_URL}/job/{run_uuid}/results/?api_key={API_KEY}"
    logging.info(f"Polling status for run_uuid: {run_uuid}")

    try:
        resp = requests.get(results_url)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as e:
        # If 400 error from /results, fetch job status for more info
        if resp.status_code == 400:
            job_url = f"{API_URL}/job/{run_uuid}/?api_key={API_KEY}"
            max_retries = 10
            for attempt in range(max_retries):
                try:
                    job_resp = requests.get(job_url)
                    job_resp.raise_for_status()
                    job_data = job_resp.json()
                    status = job_data.get("status")
                    error_message = job_data.get("message", f"Job failed with status: {status}")
                    logging.error(f"NREL job {run_uuid} failed: {error_message}")
                    return jsonify({"error": error_message, "status": status, "job": job_data}), 200
                except requests.exceptions.HTTPError as job_e:
                    if job_resp.status_code == 404 and attempt < max_retries - 1:
                        logging.warning(f"Job status 404 for run_uuid {run_uuid}, retrying ({attempt+1}/{max_retries})...")
                        time.sleep(3)
                        continue
                    logging.error(f"Error fetching job status after /results 400: {job_e}")
                    return jsonify({"error": f"Job failed and could not fetch job status: {job_e}"}), 502
                except Exception as job_e:
                    logging.error(f"Error fetching job status after /results 400: {job_e}")
                    return jsonify({"error": f"Job failed and could not fetch job status: {job_e}"}), 502
        logging.error(f"Request exception from NREL API: {e}")
        return jsonify({"error": str(e)}), 502
    except requests.exceptions.RequestException as e:
        logging.error(f"Request exception from NREL API: {e}")
        return jsonify({"error": str(e)}), 502
    except ValueError as e:
        logging.error(f"Invalid JSON received from NREL API: {e}")
        return jsonify({"error": "Invalid JSON received from NREL API"}), 502

    status = data.get("status")

    # Detect failure or error statuses
    if status in ["Failed", "Error", "Cancelled"]:
        error_message = data.get("message", "Job failed with status: " + status)
        logging.error(f"NREL job {run_uuid} failed: {error_message}")
        return jsonify({"error": error_message, "status": status}), 200

    if status == "Completed":
        results_resp = requests.get(results_url)
        try:
            results_resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTP error getting results from NREL API: {e}")
            return jsonify({"error": results_resp.json()}), results_resp.status_code
        data["outputs"] = results_resp.json().get("outputs")

    return jsonify(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
