"""Centrifuge load model utilities.

This module exposes a dataclass describing key parameters for a gas-
centrifuge enrichment plant and a helper to generate an 8760-hour load
curve.  The implementation is adapted from the research prototype in
``data/load_profiles/GeM/GeM_Load_Generation.py`` but trimmed down for
use within the Streamlit application.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Tuple
import math
import warnings

import numpy as np
import pandas as pd


@dataclass
class CentrifugeParams:
    """Input parameters for the centrifuge load model."""

    # Plant-scale production
    plant_swu_per_year: float = 1_000_000.0
    kwh_per_swu: float = 55.0
    interpret_kwh_per_swu_as_total_plant: bool = False

    # Centrifuge fleet assumptions
    machine_swu_per_year: float = 300.0
    availability: float = 0.96
    num_cascades: int = 20

    # Spin-up / restart dynamics
    daily_restart_fraction: float = 0.005
    spinup_minutes: float = 20.0
    spinup_power_factor: float = 3.5
    spinup_window_hours: Tuple[int, int] = (6, 22)

    # HVAC & Aux loads
    hvac_fraction_of_running: float = 0.30
    aux_kw_constant: float = 1500.0

    # Seasonal HVAC modulation
    hvac_seasonal_amplitude: float = 0.20
    season_peak_month: int = 7

    # Ride-through study
    ride_through_seconds: float = 20.0
    critical_fraction: float = 0.80

    # Timeframe
    year: int = 2025

    # Randomness
    random_seed: int = 42


def _seasonal_multiplier(index: pd.DatetimeIndex, peak_month: int, amplitude: float) -> np.ndarray:
    months = index.month.values
    angles = (months - peak_month) * (2.0 * np.pi / 12.0)
    return 1.0 + amplitude * np.cos(angles)


def build_centrifuge_load_curve(params: CentrifugeParams) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """Build an 8760-hour load curve for the centrifuge plant.

    Parameters
    ----------
    params : CentrifugeParams
        Model inputs.

    Returns
    -------
    df : pandas.DataFrame
        Indexed by timestamp with columns ``centrifuge_kw``, ``hvac_kw``,
        ``aux_kw``, ``spinup_kw``, ``spinup_count`` and ``total_kw``.
    summary : dict
        Key performance metrics and UPS ride-through sizing.
    """

    np.random.seed(params.random_seed)

    hours_in_year = 8760
    start = datetime(params.year, 1, 1)
    index = pd.date_range(start, periods=hours_in_year, freq="H")

    annual_kwh_target = params.plant_swu_per_year * params.kwh_per_swu

    running_mask = np.ones(hours_in_year, dtype=bool)
    num_running_hours = int(round(hours_in_year * params.availability))
    downtime_count = hours_in_year - num_running_hours
    if downtime_count > 0:
        downtime_idx = np.linspace(0, hours_in_year - 1, downtime_count, dtype=int)
        running_mask[downtime_idx] = False

    hvac_seasonal = _seasonal_multiplier(index, params.season_peak_month, params.hvac_seasonal_amplitude)

    if not params.interpret_kwh_per_swu_as_total_plant:
        avg_centrifuge_kw_all_hours = annual_kwh_target / hours_in_year
        centrifuge_running_kw_total = avg_centrifuge_kw_all_hours / max(params.availability, 1e-6)
    else:
        avg_centrifuge_kw_all_hours = annual_kwh_target / hours_in_year
        centrifuge_running_kw_total = avg_centrifuge_kw_all_hours / max(params.availability, 1e-6)

    num_centrifuges = int(math.ceil(params.plant_swu_per_year / max(params.machine_swu_per_year, 1e-9)))
    per_machine_kw = centrifuge_running_kw_total / max(num_centrifuges, 1)

    centrifuge_kw = np.where(running_mask, centrifuge_running_kw_total, 0.0)
    hvac_kw = params.hvac_fraction_of_running * centrifuge_kw * hvac_seasonal
    aux_kw = np.full(hours_in_year, params.aux_kw_constant, dtype=float)

    spinup_kw = np.zeros(hours_in_year, dtype=float)
    spinup_count = np.zeros(hours_in_year, dtype=int)

    machines_per_day_restart = int(round(params.daily_restart_fraction * num_centrifuges))
    window_start, window_end = params.spinup_window_hours
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
        counts: Dict[int, int] = {}
        for h in chosen_hours:
            counts[h] = counts.get(h, 0) + 1
        for h, count in counts.items():
            hour_idx = day * 24 + h
            if 0 <= hour_idx < hours_in_year and running_mask[hour_idx]:
                spinup_kw[hour_idx] += count * extra_kw_per_machine * minutes_frac
                spinup_count[hour_idx] += count

    total_kw = centrifuge_kw + hvac_kw + aux_kw + spinup_kw

    if params.interpret_kwh_per_swu_as_total_plant:
        target_annual_kwh = annual_kwh_target
        current_annual_kwh = float(total_kw.sum())
        if current_annual_kwh > 0:
            scale = target_annual_kwh / current_annual_kwh
            centrifuge_kw *= scale
            hvac_kw *= scale
            aux_kw *= scale
            spinup_kw *= scale
            total_kw *= scale
            centrifuge_running_kw_total *= scale
            per_machine_kw *= scale
        else:
            warnings.warn("Total kWh computed as zero; scaling skipped.")

    p90 = float(np.percentile(total_kw, 90))
    critical_kw = params.critical_fraction * p90
    ups_kwh_required = critical_kw * (params.ride_through_seconds / 3600.0)

    df = pd.DataFrame(
        {
            "running_mask": running_mask.astype(int),
            "centrifuge_kw": centrifuge_kw,
            "hvac_kw": hvac_kw,
            "aux_kw": aux_kw,
            "spinup_kw": spinup_kw,
            "spinup_count": spinup_count,
            "total_kw": total_kw,
        },
        index=index,
    )

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
        "critical_fraction": params.critical_fraction,
    }
    return df, summary
