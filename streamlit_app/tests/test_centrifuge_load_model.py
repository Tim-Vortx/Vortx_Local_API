import sys
from pathlib import Path
import json
from dataclasses import asdict

# Ensure repo root and streamlit_app are on sys.path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
if str(ROOT / "streamlit_app") not in sys.path:
    sys.path.append(str(ROOT / "streamlit_app"))

from data.load_profiles.GeM.GeM_Load_Generation import (
    build_centrifuge_load_curve,
    CentrifugeParams,
)


def test_build_centrifuge_load_curve_returns_expected_shape_and_summary():
    df, summary = build_centrifuge_load_curve(CentrifugeParams())
    assert len(df) == 8760
    expected_keys = {
        "plant_swu_per_year",
        "kwh_per_swu",
        "num_centrifuges",
        "annual_mwh",
        "estimated_ups_kwh_required_for_ridethrough",
    }
    assert expected_keys.issubset(summary.keys())


def test_centrifuge_params_json_roundtrip_and_ignore_unknown():
    params = CentrifugeParams()
    data = asdict(params)
    data["extra_field"] = 12345
    json_str = json.dumps(data)
    loaded = json.loads(json_str)
    known = {k: v for k, v in loaded.items() if k in asdict(CentrifugeParams())}
    if isinstance(known.get("spinup_window_hours"), list):
        known["spinup_window_hours"] = tuple(known["spinup_window_hours"])
    reconstructed = CentrifugeParams(**known)
    assert reconstructed == params
