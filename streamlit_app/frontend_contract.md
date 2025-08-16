Frontend-backend minimal contract

This document describes the small, stable subset of fields the Streamlit UI must supply to the FastAPI backend so REopt (Julia) receives a valid scenario payload.

Top-level keys (required):
- Settings: dict
  - time_steps_per_hour: int (default 1)
  - off_grid_flag: bool (optional, default false)

- Site: dict (recommended fields)
  - latitude: float
  - longitude: float
  - year: int (optional, fallback 2017)

- ElectricLoad: dict (required)
  - loads_kw: array of numeric values length == 8760 * time_steps_per_hour
    OR
  - hourly_profile: alias for loads_kw (backend will normalize)
  - time_steps_per_hour: int (optional, backend will default to Settings.time_steps_per_hour or 1)
  - year: int (optional, backend will fallback to Site.year or 2017)
  - off_grid_flag: bool (optional; Settings.off_grid_flag is used as fallback)

- ElectricTariff: dict (required for on-grid)
  - Provide one of the following shapes:
    - urdb_label (string) or urdb_response (dict)
    - blended_annual_energy_rate (float) for a single annual average cost
    - monthly_energy_rates (array length 12) for monthly blended rates
    - tou_energy_rates_per_kwh (array length 8760 * time_steps_per_hour) for full timeseries
  - Optional: NEM (bool), wholesale_rate, export_rate_beyond_net_metering_limit, monthly_demand_rates

Notes
- Backend will normalize `hourly_profile` -> `loads_kw` and validate length.
- Backend will enforce `operating_reserve_required_fraction = 0.0` for on-grid scenarios; set `off_grid_flag` in `Settings` or `ElectricLoad` to mark off-grid.
- If an array length mismatch or invalid type is detected for `loads_kw`, backend will return an error and write a clear `status.json`.

If you want, the frontend can be updated to produce this exact shape to reduce server-side normalization.
