from flask import Flask, request, jsonify
from flask_cors import CORS
import os, requests
from dotenv import load_dotenv

load_dotenv()  # reads .env
API_KEY = os.getenv("NREL_API_KEY")
BASE = "https://developer.nrel.gov/api/reopt/v3/job"

app = Flask(__name__)
CORS(app)  # allow React dev-server to call us

@app.route("/submit", methods=["POST"])
def submit():
    scenario = request.json
    # wrap per v3 spec
    resp = requests.post(f"{BASE}?api_key={API_KEY}", json={"Scenario": scenario})
    resp.raise_for_status()
    run_uuid = resp.json()["data"]["run_uuid"]
    return jsonify({"run_uuid": run_uuid})

@app.route("/status/<run_uuid>", methods=["GET"])
def status(run_uuid):
    resp = requests.get(f"{BASE}/{run_uuid}?api_key={API_KEY}")
    resp.raise_for_status()
    return jsonify(resp.json())

if __name__ == "__main__":
    # ensure this matches your React proxy
    app.run(port=5000, debug=True)
