from flask import Flask, request, jsonify
from flask_cors import CORS
import os, requests
from dotenv import load_dotenv

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
    scenario = request.json
    post_url = f"{API_URL}/job/?api_key={API_KEY}"
    resp = None
    try:
        resp = requests.post(post_url, json={"Scenario": scenario})
        resp.raise_for_status()
        data = resp.json()
        run_uuid = data["data"]["run_uuid"]
    except (requests.exceptions.RequestException, KeyError) as e:
        # Surface any error message from NREL or request issues
        err_resp = getattr(e, "response", resp)
        try:
            err = err_resp.json()
        except Exception:
            err = getattr(err_resp, "text", str(e))
        status = getattr(err_resp, "status_code", 500)
        return jsonify({"error": err}), status

    return jsonify({"run_uuid": run_uuid})

@app.route("/status/<run_uuid>", methods=["GET"])
def status(run_uuid):
    job_url = f"{API_URL}/job/{run_uuid}/?api_key={API_KEY}"
    resp = requests.get(job_url)
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        return jsonify({"error": resp.json()}), resp.status_code

    data = resp.json()
    if data.get("status") == "Completed":
        results_url = f"{API_URL}/job/{run_uuid}/results/?api_key={API_KEY}"
        results_resp = requests.get(results_url)
        try:
            results_resp.raise_for_status()
        except requests.exceptions.HTTPError:
            return jsonify({"error": results_resp.json()}), results_resp.status_code
        data["outputs"] = results_resp.json().get("outputs")

    return jsonify(data)

if __name__ == "__main__":
    # ensure this matches your React proxy
    app.run(port=5000, debug=True)
