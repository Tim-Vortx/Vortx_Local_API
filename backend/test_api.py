import time
import os
import json
import pytest
from fastapi.testclient import TestClient
from backend.api import app

client = TestClient(app)

def test_run_and_poll_for_result():
    print("Starting test_run_and_poll_for_result...")
    # Load the real 8760-hour profile from the .dat file
    dat_path = os.path.join(os.path.dirname(__file__), "../data/load_profiles/electric/crb8760_norm_Albuquerque_LargeOffice.dat")
    with open(dat_path) as f:
        loads_kw = [float(line.strip()) for line in f if line.strip()]
    assert len(loads_kw) == 8760, f"Expected 8760 values, got {len(loads_kw)}"
    payload = {
        "Site": {"latitude": 40.0, "longitude": -105.0},
        "ElectricLoad": {"loads_kw": loads_kw, "year": 2024},
        "ElectricTariff": {
            "blended_annual_energy_rate": 0.06,
            "blended_annual_demand_rate": 0.0
        }
    }
    response = client.post("/reopt/run", json=payload)
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    print(f"Submitted job with run_id: {run_id}")

    # Poll every 10 seconds, up to 5 minutes (30 polls)
    import datetime
    for i in range(30):
        result_response = client.get(f"/reopt/result/{run_id}")
        assert result_response.status_code == 200
        data = result_response.json()
        now = datetime.datetime.now().strftime('%H:%M:%S')
        print(f"[{now}] Poll {i+1}: status = {data.get('status')}, full response: {data}")
        if data.get("status") == "completed":
            print("Job completed!")
            assert "result" in data
            break
        elif data.get("status") == "error":
            print(f"Job failed: {data}")
            assert False, f"Job failed: {data}"
        time.sleep(10)
    else:
        print("Timeout waiting for job to complete")
        assert False, "Timeout waiting for job to complete"
def test_run_reopt_valid_payload():
    dat_path = os.path.join(os.path.dirname(__file__), "../data/load_profiles/electric/crb8760_norm_Albuquerque_LargeOffice.dat")
    with open(dat_path) as f:
        loads_kw = [float(line.strip()) for line in f if line.strip()]
    assert len(loads_kw) == 8760, f"Expected 8760 values, got {len(loads_kw)}"
    payload = {
        "Site": {"latitude": 40.0, "longitude": -105.0},
        "ElectricLoad": {"loads_kw": loads_kw, "year": 2024},
        "ElectricTariff": {
            "blended_annual_energy_rate": 0.06,
            "blended_annual_demand_rate": 0.0
        }
    }
    response = client.post("/reopt/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    run_id = data.get("run_id")
    print(f"Submitted job with run_id: {run_id}")
    assert "run_id" in data


def test_run_reopt_missing_body():
    response = client.post("/reopt/run")
    assert response.status_code == 422  # Unprocessable Entity for missing body



    response = client.get("/reopt/result/invalid_id")
    assert response.status_code == 404

# Add more tests for valid/invalid payloads as needed

def test_run_reopt():
    """Test the /reopt/run endpoint with a valid scenario."""
    scenario = {
        "Site": {"latitude": 34.05, "longitude": -118.25},
        "ElectricLoad": {
            "loads_kw": [1500.0] * 8760,
            "year": 2025,
            "time_steps_per_hour": 1,
        },
        "ElectricTariff": {"time_steps_per_hour": 1, "year": 2025, "NEM": False},
        "Financial": {
            "analysis_years": 25,
            "offtaker_discount_rate_fraction": 0.08,
            "elec_cost_escalation_rate_fraction": 0.025,
            "om_cost_escalation_rate_fraction": 0.025,
            "offtaker_tax_rate_fraction": 0.26,
            "third_party_ownership": False,
        },
    }

    response = client.post("/reopt/run", json=scenario)
    assert response.status_code == 200
    assert "run_id" in response.json()

def test_run_reopt_invalid_scenario():
    """Test the /reopt/run endpoint with an invalid scenario."""
    scenario = {"InvalidKey": "InvalidValue"}

    response = client.post("/reopt/run", json={"scenario": scenario})
    assert response.status_code == 422
