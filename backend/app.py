from flask import Flask, request, jsonify
from flask_cors import CORS
import os, requests
from dotenv import load_dotenv
from werkzeug.exceptions import BadRequest

load_dotenv()  # reads .env
API_KEY = os.getenv("NREL_API_KEY")
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
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        scenario = request.get_json()
    except BadRequest:
        return jsonify({"error": "Malformed JSON in request"}), 400

    post_url = f"{API_URL}/job/?api_key={API_KEY}"
    try:
        resp = requests.post(post_url, json={"Scenario": scenario})
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        # covers HTTPError and network issues
        return jsonify({"error": str(e)}), 502
    except ValueError:
        return jsonify({"error": "Invalid JSON received from NREL API"}), 502

    run_uuid = data.get("data", {}).get("run_uuid")
    if not run_uuid:
        return jsonify({"error": "run_uuid missing from NREL response"}), 502
    return jsonify({"run_uuid": run_uuid})

@app.route("/status/<run_uuid>", methods=["GET"])
def status(run_uuid):
    results_url = f"{API_URL}/job/{run_uuid}/results/?api_key={API_KEY}"
    try:
        resp = requests.get(results_url)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 502
    except ValueError:
        return jsonify({"error": "Invalid JSON received from NREL API"}), 502

    return jsonify(data)

if __name__ == "__main__":
    # ensure this matches your React proxy
    app.run(port=5000, debug=True)
