import pandas as pd

SUPPLY_KEYS = [
    ("ElectricUtility", "electric_to_load_series_kw", "Utility"),
    ("PV", "electric_to_load_series_kw", "Solar → Load"),
    ("ElectricStorage", "electric_to_load_series_kw", "BESS → Load"),
    ("Generator", "electric_to_load_series_kw", "Diesel → Load"),
    ("CHP", "electric_to_load_series_kw", "NG (CHP) → Load"),
]

def _get_series(results, section, key):
    try:
        return results.get(section, {}).get(key, [])
    except Exception:
        return []

def to_daily_series(results: dict, day_index=0, tph=1):
    steps = 24 * tph
    start = day_index * steps

    def sl(x):
        return x[start:start+steps] if isinstance(x, list) else [0]*steps

    load = sl(results.get("ElectricLoad", {}).get("load_series_kw", []))
    data = {"hour": [i/tph for i in range(steps)], "load": load}

    for sec, k, label in SUPPLY_KEYS:
        data[label] = sl(_get_series(results, sec, k))

    import pandas as pd
    return pd.DataFrame(data)

def monthly_rollup(results: dict) -> pd.DataFrame:
    # 8760 hourly index; if not provided, just return zeros
    load = results.get("ElectricLoad", {}).get("load_series_kw", [])
    if not load:
        idx = pd.date_range("2024-01-01", periods=8760, freq="H")
    else:
        idx = pd.date_range("2024-01-01", periods=len(load), freq="H")

    def s(sec, key):
        arr = results.get(sec, {}).get(key, [])
        if not arr:
            return pd.Series([0]*len(idx), index=idx)
        return pd.Series(arr, index=idx)

    pv_total = s("PV","electric_to_load_series_kw") + s("PV","electric_to_grid_series_kw") + s("PV","electric_to_storage_series_kw")
    bess_dis = s("ElectricStorage","electric_to_load_series_kw") + s("ElectricStorage","electric_to_grid_series_kw")
    diesel   = s("Generator","electric_to_load_series_kw")
    chp      = s("CHP","electric_to_load_series_kw")

    df = pd.DataFrame({
        "PV_total_MWh": pv_total.resample("MS").sum() / 1000.0,
        "BESS_discharge_MWh": bess_dis.resample("MS").sum() / 1000.0,
        "Diesel_gen_MWh": diesel.resample("MS").sum() / 1000.0,
        "CHP_gen_MWh": chp.resample("MS").sum() / 1000.0,
    })
    df.index = df.index.strftime("%b")
    df.reset_index(inplace=True)
    df.rename(columns={"index":"Month"}, inplace=True)
    return df
