"""
centrifuge_load_model.py

A parameterized 8760-hour load model for gas-centrifuge uranium enrichment cascades.
Designed to drop into a REopt (or other) modeling stack.

What it does
------------
- Generates hourly kW for:
  - centrifuge running load
  - HVAC load (scales with centrifuge load + seasonal modulation)
  - auxiliary constant load
  - spin-up/restart transients
- Produces a pandas DataFrame (8760 rows) and a summary dictionary.
- Optional export to CSV/XLSX.

Key assumptions (adjustable in `CentrifugeParams`):
- Electricity intensity: default 55 kWh/SWU (modern centrifuge plants often 50–60).
- Per-machine SWU/yr: default 300 (adjust to vendor).
- Availability: fraction of hours centrifuges are running.
- Spin-up minutes and power multiplier.
- HVAC fraction vs. centrifuge running load + seasonal swing.
- Auxiliary constant kW.
- Ride-through sizing for UPS (kWh for N seconds for critical load fraction).

NOTE on interpretation of kWh/SWU
---------------------------------
This module, by default, interprets `kwh_per_swu` as applying to the **centrifuge running load only**,
and then adds HVAC and AUX on top. If you want `kwh_per_swu` to represent **total plant**
(consuming centrifuge + HVAC + AUX), set `interpret_kwh_per_swu_as_total_plant=True` and the model
will scale centrifuge vs. HVAC/AUX proportionally to meet the plant-wide annual energy target.

Author: ChatGPT (GPT-5 Thinking)
License: MIT
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Dict, Optional
import math
import numpy as np
import pandas as pd
from datetime import datetime
import warnings

try:
    import xlsxwriter  # noqa: F401  # Optional for XLSX export
    _HAVE_XLSX = True
except Exception:
    _HAVE_XLSX = False

__all__ = ["CentrifugeParams", "build_centrifuge_load_curve", "save_outputs"]


@dataclass
class CentrifugeParams:
    # Plant-scale production
    plant_swu_per_year: float = 1_000_000.0     # total separative work units per year
    kwh_per_swu: float = 55.0                   # electricity intensity [kWh/SWU]
    interpret_kwh_per_swu_as_total_plant: bool = False  # if True, total plant kWh matches plant_swu*kwh_per_swu

    # Centrifuge fleet assumptions
    machine_swu_per_year: float = 300.0         # per-centrifuge SWU output per year
    availability: float = 0.96                  # fraction of time centrifuges are running (0..1)
    num_cascades: int = 20                      # for potential scheduling (not used heavily in base model)

    # Spin-up / restart dynamics
    daily_restart_fraction: float = 0.005       # fraction of machines restarted per day (0.5% default)
    spinup_minutes: float = 20.0                # minutes to spin up a centrifuge
    spinup_power_factor: float = 3.5            # multiple of steady-state power during spin-up
    spinup_window_hours: Tuple[int, int] = (6, 22)  # hours [start, end) for planned restarts

    # HVAC & Aux loads
    hvac_fraction_of_running: float = 0.30      # HVAC as % of centrifuge running kW (average)
    aux_kw_constant: float = 1500.0             # constant site loads (security, UF6 handling, etc.)

    # Seasonal HVAC modulation
    hvac_seasonal_amplitude: float = 0.20       # +/- swing around hvac_fraction (0.2 = +/-20%)
    season_peak_month: int = 7                  # 1..12 (7=July)

    # Ride-through study
    ride_through_seconds: float = 20.0          # UPS ride-through seconds for critical loads
    critical_fraction: float = 0.80             # fraction of load that must ride through

    # Timeframe
    year: int = 2025                            # non-leap year recommended for 8760 simplification

    # Randomness
    random_seed: int = 42                       # for reproducible restart scheduling


def _seasonal_multiplier(index: pd.DatetimeIndex, peak_month: int, amplitude: float) -> np.ndarray:
    months = index.month.values
    # cosine with peak at peak_month
    angles = (months - peak_month) * (2.0 * np.pi / 12.0)
    return 1.0 + amplitude * np.cos(angles)


def build_centrifuge_load_curve(params: CentrifugeParams) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Build an 8760 load curve for centrifuge cascades with HVAC/AUX and spin-up transients.

    Returns
    -------
    df : pandas.DataFrame (indexed by timestamp)
        Columns: running_mask, centrifuge_kw, hvac_kw, aux_kw, spinup_kw, spinup_count, total_kw
    summary : dict
        Key performance metrics and UPS ride-through sizing.
    """
    np.random.seed(params.random_seed)

    hours_in_year = 8760  # assume non-leap year
    start = datetime(params.year, 1, 1)
    index = pd.date_range(start, periods=hours_in_year, freq="H")

    # Annual energy target (kWh)
    annual_kwh_target = params.plant_swu_per_year * params.kwh_per_swu

    # Running vs downtime mask
    running_mask = np.ones(hours_in_year, dtype=bool)
    num_running_hours = int(round(hours_in_year * params.availability))
    # distribute downtime approximately uniformly
    downtime_count = hours_in_year - num_running_hours
    if downtime_count > 0:
        downtime_idx = np.linspace(0, hours_in_year - 1, downtime_count, dtype=int)
        running_mask[downtime_idx] = False

    # Seasonal HVAC modulation
    hvac_seasonal = _seasonal_multiplier(index, params.season_peak_month, params.hvac_seasonal_amplitude)

    # Compute centrifuge running kW base
    # Two modes:
    #  (A) kWh/SWU applies to centrifuge-only energy -> HVAC/AUX are added on top
    #  (B) kWh/SWU applies to TOTAL plant -> scale centrifuge/HVAC/AUX to meet annual target
    # First compute centrifuge-only running baseline (ignoring HVAC/AUX):
    hours_running = max(num_running_hours, 1)
    centrifuge_running_kwh_needed = annual_kwh_target if not params.interpret_kwh_per_swu_as_total_plant else None

    if not params.interpret_kwh_per_swu_as_total_plant:
        # Mode A: kWh/SWU is centrifuge-only
        # Average centrifuge kW over ALL hours to hit centrifuge energy target:
        avg_centrifuge_kw_all_hours = annual_kwh_target / hours_in_year
        # But when running (availability < 100%), running kW must be higher to hit the same energy target:
        centrifuge_running_kw_total = avg_centrifuge_kw_all_hours / max(params.availability, 1e-6)
    else:
        # Mode B: We'll back-solve to meet total plant energy target after adding HVAC/AUX.
        # Start with a provisional running kW for centrifuge, then scale later.
        # Use the same structure as Mode A but mark for scaling at the end.
        avg_centrifuge_kw_all_hours = annual_kwh_target / hours_in_year
        centrifuge_running_kw_total = avg_centrifuge_kw_all_hours / max(params.availability, 1e-6)

    # Per-machine steady-state kW (informational, also used for spin-up calc)
    num_centrifuges = int(math.ceil(params.plant_swu_per_year / max(params.machine_swu_per_year, 1e-9)))
    per_machine_kw = centrifuge_running_kw_total / max(num_centrifuges, 1)

    # Base centrifuge hourly profile (no spin-up yet)
    centrifuge_kw = np.where(running_mask, centrifuge_running_kw_total, 0.0)

    # HVAC based on centrifuge running load (scaled by seasonal modulation)
    hvac_kw = params.hvac_fraction_of_running * centrifuge_kw * hvac_seasonal

    # AUX constant
    aux_kw = np.full(hours_in_year, params.aux_kw_constant, dtype=float)

    # Spin-up model
    spinup_kw = np.zeros(hours_in_year, dtype=float)
    spinup_count = np.zeros(hours_in_year, dtype=int)

    machines_per_day_restart = int(round(params.daily_restart_fraction * num_centrifuges))
    window_start, window_end = params.spinup_window_hours
    # ensure proper window
    window_start = max(0, min(23, int(window_start)))
    window_end = max(1, min(24, int(window_end)))
    if window_end <= window_start:
        window_end = min(window_start + 1, 24)
    spinup_hours = list(range(window_start, window_end))

    minutes_frac = params.spinup_minutes / 60.0
    extra_kw_per_machine = (params.spinup_power_factor - 1.0) * per_machine_kw

    for day in range(365):
        if machines_per_day_restart <= 0 or not spinup_hours:
            continue
        chosen_hours = np.random.choice(spinup_hours, size=machines_per_day_restart, replace=True)
        # aggregate counts per hour
        counts = {}
        for h in chosen_hours:
            counts[h] = counts.get(h, 0) + 1
        for h, count in counts.items():
            hour_idx = day * 24 + h
            if 0 <= hour_idx < hours_in_year and running_mask[hour_idx]:
                spinup_kw[hour_idx] += count * extra_kw_per_machine * minutes_frac
                spinup_count[hour_idx] += count

    # Total (pre-scaling)
    total_kw = centrifuge_kw + hvac_kw + aux_kw + spinup_kw

    if params.interpret_kwh_per_swu_as_total_plant:
        # Scale entire load so that total annual energy == plant_swu * kwh_per_swu
        target_annual_kwh = annual_kwh_target
        current_annual_kwh = float(total_kw.sum())
        if current_annual_kwh > 0:
            scale = target_annual_kwh / current_annual_kwh
            centrifuge_kw *= scale
            hvac_kw *= scale
            aux_kw *= scale
            spinup_kw *= scale
            total_kw *= scale
            # Recompute per-machine kW after scaling (informational)
            centrifuge_running_kw_total *= scale
            per_machine_kw *= scale
        else:
            warnings.warn("Total kWh computed as zero; scaling skipped.")

    # UPS ride-through sizing (kWh) at 90th percentile load and critical fraction
    p90 = float(np.percentile(total_kw, 90))
    critical_kw = params.critical_fraction * p90
    ups_kwh_required = critical_kw * (params.ride_through_seconds / 3600.0)

    df = pd.DataFrame({
        "running_mask": running_mask.astype(int),
        "centrifuge_kw": centrifuge_kw,
        "hvac_kw": hvac_kw,
        "aux_kw": aux_kw,
        "spinup_kw": spinup_kw,
        "spinup_count": spinup_count,
        "total_kw": total_kw
    }, index=index)

    summary = {
        "plant_swu_per_year": params.plant_swu_per_year,
        "kwh_per_swu": params.kwh_per_swu,
        "interpret_kwh_per_swu_as_total_plant": params.interpret_kwh_per_swu_as_total_plant,
        "machine_swu_per_year": params.machine_swu_per_year,
        "num_centrifuges": num_centrifuges,
        "availability": params.availability,
        "avg_kw_over_year": float(np.mean(total_kw)),
        "peak_kw": float(np.max(total_kw)),
        "p95_kw": float(np.percentile(total_kw, 95)),
        "p50_kw": float(np.percentile(total_kw, 50)),
        "annual_mwh": float(np.sum(total_kw) / 1000.0),
        "estimated_ups_kwh_required_for_ridethrough": float(ups_kwh_required),
        "ups_ridethrough_seconds": params.ride_through_seconds,
        "critical_fraction": params.critical_fraction
    }
    return df, summary


def save_outputs(df: pd.DataFrame, summary: Dict[str, float],
                 csv_path: Optional[str] = None,
                 xlsx_path: Optional[str] = None) -> None:
    """Save results to CSV/XLSX (summary in separate sheet for XLSX)."""
    if csv_path:
        df.to_csv(csv_path, index=True)
    if xlsx_path:
        if not _HAVE_XLSX:
            warnings.warn("xlsxwriter not available; skipping XLSX export.")
            return
        with pd.ExcelWriter(xlsx_path, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="load_profile")
            pd.DataFrame([summary]).to_excel(writer, sheet_name="summary", index=False)
