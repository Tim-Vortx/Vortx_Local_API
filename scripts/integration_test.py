import requests
import time
import json

# Load your scenario (with 8760-hour load profile)
with open("scenario_from_dat.json") as f:
    payload = json.load(f)

# 1. Submit the job
resp = requests.post("http://127.0.0.1:8000/reopt/run", json=payload)
resp.raise_for_status()
run_id = resp.json()["run_id"]
print(f"Submitted job with run_id: {run_id}")

# 2. Poll for results
for i in range(30):  # Poll every 10s for up to 5 minutes
    time.sleep(10)
    r = requests.get(f"http://127.0.0.1:8000/reopt/result/{run_id}")
    print(f"Poll {i+1}: status = {r.json().get('status')}")
    if r.json().get("status") == "completed":
        print("Job completed!")
        print(json.dumps(r.json(), indent=2))
        break
    elif r.json().get("status") == "error":
        print("Job failed:", r.json())
        break
else:
    print("Timeout waiting for job to complete")
