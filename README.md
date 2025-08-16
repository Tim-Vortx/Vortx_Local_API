# REopt® Julia package
REopt.jl is the core module of the [REopt® techno-economic decision support platform](https://www.nrel.gov/reopt/), developed by the National Renewable Energy Laboratory (NREL). REopt® stands for **R**enewable **E**nergy integration and **opt**imization. REopt.jl is used within the publicly-accessible and open-source [REopt API](https://github.com/NREL/REopt_API), and the publicly available [REopt Web Tool](https://reopt.nrel.gov/tool) calls the REopt API.

The REopt® techno-economic decision support platform is used by researchers to optimize energy systems for buildings, campuses, communities, microgrids, and more. REopt identifies the optimal mix of renewable energy, conventional generation, storage, and electrification technologies to meet cost savings, resilience, emissions reductions, and energy performance goals.

For more information about REopt.jl please see the Julia documentation:
<!-- [![](https://img.shields.io/badge/docs-stable-blue.svg)](https://nrel.github.io/REopt.jl/stable) -->
[![](https://img.shields.io/badge/docs-dev-blue.svg)](https://nrel.github.io/REopt.jl/dev)


## Quick Start
Evaluating simple `PV` and `ElectricStorage` scenarios requires a linear program solver. Evaluating net-metering, `Generator`, multiple outages, or other more complex scenario makes the problem mixed-integer linear, and thus requires a MILP solver. See https://jump.dev/JuMP.jl/stable/installation/ for a list of solvers. The REopt package has been tested with , `HiGHS`, `Cbc`, `SCIP`, `Xpress` (commercial), and `CPLEX` (commercial).

### Example
```
using REopt, JuMP, HiGHS

m = Model(HiGHS.Optimizer)
results = run_reopt(m, "pv_storage.json")
```
See the `test/scenarios` directory for examples of `scenario.json`.

For more details, including installation instructions, see the [documentation](https://nrel.github.io/REopt.jl/dev).

## Local API Server

A simple FastAPI service is provided in `backend/api.py` to run REopt models.

### Endpoints
- `POST /reopt/run`: submit a scenario JSON body. Optional `solver` query parameter overrides the default solver.
- `GET /reopt/result/{run_id}`: fetch run status or results.

### Environment setup
Before using the API, instantiate Julia dependencies and install a solver:
```
julia --project=. -e 'using Pkg; Pkg.instantiate()'
julia --project=. -e 'using Pkg; Pkg.add("HiGHS")'
```

### Configuration
These environment variables adjust runtime behavior:
- `REOPT_PROJECT_ROOT`: path to the REopt project (default: repository root).
- `REOPT_RUNS_DIR`: directory for run metadata and results (default: `backend/runs`).
- `REOPT_SOLVER`: default solver passed to Julia (default: `HiGHS`).

### Running the server
Start the API locally with:
```
uvicorn backend.reopt_api_client:app --reload
```

Submit a scenario and retrieve results:
```
curl -X POST 'http://localhost:8000/reopt/run?solver=HiGHS' \
     -H 'Content-Type: application/json' \
     -d @scenario.json
curl http://localhost:8000/reopt/result/<run_id>
```
