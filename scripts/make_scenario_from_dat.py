import json

# Path to your .dat file
load_file = "data/load_profiles/electric/crb8760_norm_Albuquerque_LargeOffice.dat"

# Read the load profile (assuming one value per line)
with open(load_file) as f:
    loads_kw = [float(line.strip()) for line in f if line.strip()]

assert len(loads_kw) == 8760, f"Expected 8760 values, got {len(loads_kw)}"

scenario = {
    "Site": {"latitude": 40.0, "longitude": -105.0},
    "ElectricLoad": {"loads_kw": loads_kw, "year": 2024},
    "ElectricTariff": {
        "blended_annual_energy_rate": 0.06,
        "blended_annual_demand_rate": 0.0
    }
}

with open("scenario_from_dat.json", "w") as f:
    json.dump(scenario, f)

print("Wrote scenario_from_dat.json with 8760-hour load profile.")
