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
    # wrap per REopt v3 spec
    post_url = f"{API_URL}/job/?api_key={API_KEY}"
    resp = requests.post(post_url, json={"Scenario": scenario})
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        return jsonify({"error": resp.json()}), resp.status_code

    run_uuid = resp.json()["data"]["run_uuid"]
    return jsonify({"run_uuid": run_uuid})

@app.route("/status/<run_uuid>", methods=["GET"])
def status(run_uuid):
    results_url = f"{API_URL}/job/{run_uuid}/results/?api_key={API_KEY}"
    resp = requests.get(results_url)
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        return jsonify({"error": resp.json()}), resp.status_code

    return jsonify(resp.json())

if __name__ == "__main__":
    # ensure this matches your React proxy
    app.run(port=5000, debug=True)
