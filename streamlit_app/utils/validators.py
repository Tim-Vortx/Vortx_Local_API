def _valid_tariff(scn: dict) -> bool:
    et = scn.get("ElectricTariff", {}) or {}
    return any([
        "urdb_label" in et,
        ("blended_annual_energy_rate" in et and "blended_annual_demand_rate" in et),
        ("monthly_energy_rates" in et and "monthly_demand_rates" in et),
        "tou_energy_rates_per_kwh" in et,
        "urdb_response" in et,
        ("urdb_utility_name" in et and "urdb_rate_name" in et),
    ])

def _validate_load(scn: dict) -> str | None:
    el = scn.get("ElectricLoad", {}) or {}
    loads, doe = el.get("loads_kw"), el.get("doe_reference_name")
    tph = scn.get("Settings", {}).get("time_steps_per_hour", 1)
    if loads and doe:
        return "Choose either DOE reference OR upload 8760 loads (not both)."
    if loads and len(loads) != 8760 * tph:
        return f"loads_kw length must be {8760 * tph}."
    return None

def build_reopt_scenario(state: dict) -> tuple[dict, list]:
    """
    Translate Streamlit session_state into a REopt-ready scenario.
    Expects the input cards to have populated these keys in session_state.
    """
    errors = []
    scn = {
        "Settings": {"time_steps_per_hour": 1, "off_grid_flag": False},
        "Site": {},
        "ElectricLoad": {},
        "ElectricTariff": {},
        "PV": {},
        "ElectricStorage": {},
        "Financial": {}
    }

    # Support two session layouts:
    # 1) legacy flat keys: session_state contains keys like 'ElectricLoad', 'latitude', etc.
    # 2) nested scenario: session_state['scenario'] contains the app's assembled scenario dict
    nested = state.get("scenario") if isinstance(state.get("scenario"), dict) else {}

    def sget(key, default=None):
        # prefer nested scenario values, fall back to top-level state safely
        if isinstance(nested, dict) and key in nested:
            return nested.get(key, default)
        if isinstance(state, dict):
            return state.get(key, default)
        return default

    def card(key):
        # return a card dict either from nested scenario or top-level session state
        if isinstance(nested, dict) and key in nested:
            return nested.get(key) or {}
        if isinstance(state, dict):
            return state.get(key) or {}
        return {}

    # Settings / Site
    settings = scn["Settings"]
    site = scn["Site"]
    settings["time_steps_per_hour"] = sget("time_steps_per_hour", 1)
    settings["off_grid_flag"] = (
        (sget("grid_connection") == "Off-Grid")
        or bool(sget("off_grid_flag", False))
        or bool(card("Settings").get("off_grid_flag"))
    )
    # Allow the user to enter a 'site_location' free-text field containing either 'lat, lon' or a 5-digit ZIP
    site_loc = sget("site_location") or card("Site").get("site_location")
    lat = sget("latitude") or card("Site").get("latitude")
    lon = sget("longitude") or card("Site").get("longitude")
    # simple ZIP resolver map (small built-in list for quick testing)
    zip_map = {
        "80302": (40.0150, -105.2705),  # Boulder, CO
        "94103": (37.7726, -122.4090),  # San Francisco, CA
        "20001": (38.9101, -77.0147),   # Washington, DC
        "10001": (40.7506, -73.9972),   # New York, NY
    }
    parsed = False
    if site_loc and isinstance(site_loc, str):
        s = site_loc.strip()
        # try lat, lon
        if "," in s:
            parts = [p.strip() for p in s.split(",")][:2]
            try:
                lat = float(parts[0]); lon = float(parts[1]); parsed = True
            except Exception:
                parsed = False
        # try 5-digit ZIP
        if not parsed and s.isdigit() and len(s) == 5:
            if s in zip_map:
                lat, lon = zip_map[s]
                parsed = True
    site["latitude"] = lat
    site["longitude"] = lon

    # Load
    el = scn["ElectricLoad"]
    el_state = card("ElectricLoad")
    if "loads_kw" in el_state:
        el["loads_kw"] = el_state["loads_kw"]
        el["year"] = el_state.get("year", 2024)
    else:
        # Support synthetic inputs: peak_kw + load_factor → generate loads_kw
        peak = el_state.get("peak_kw") or sget("peak_kw")
        lf = el_state.get("load_factor") or sget("load_factor")
        tph = scn.get("Settings", {}).get("time_steps_per_hour", 1)
        if peak and lf is not None:
            try:
                peak_f = float(peak)
                lf_f = float(lf)
                total_steps = 8760 * int(tph)
                base = peak_f * 0.1
                amp = peak_f - base
                profile = []
                for step in range(total_steps):
                    hour = (step / tph) % 24
                    x = 0.5 * (1 + __import__("math").cos((hour - 16) / 24.0 * 2 * __import__("math").pi))
                    val = base + x * amp
                    profile.append(val)
                # scale to match annual energy = peak * lf * 8760
                annual_kwh = peak_f * lf_f * 8760.0
                current_sum = sum(profile)
                scale = (annual_kwh / current_sum) if current_sum > 0 else 1.0
                profile = [v * scale for v in profile]
                el["loads_kw"] = profile
                el["year"] = el_state.get("year", 2024)
                el["peak_kw"] = peak_f
                el["load_factor"] = lf_f
            except Exception:
                # fallback to legacy DOE-style fields if synthesis fails
                el["doe_reference_name"] = sget("doe_reference_name") or el_state.get("doe_reference_name") or "LargeOffice"
                el["annual_kwh"] = sget("annual_kwh") or el_state.get("annual_kwh", 1_500_000)
        else:
            el["doe_reference_name"] = sget("doe_reference_name") or el_state.get("doe_reference_name") or "LargeOffice"
            el["annual_kwh"] = sget("annual_kwh") or el_state.get("annual_kwh", 1_500_000)

    # Tariff
    et = scn["ElectricTariff"]
    if not settings["off_grid_flag"]:
        # Prefer a URDB label if the Grid card set one in session
        urdb_label = state.get("urdb_label") or state.get("ElectricTariff", {}).get("urdb_label")
        if urdb_label:
            et["urdb_label"] = urdb_label
        else:
            # fallback blended
            et["blended_annual_energy_rate"] = state.get("blended_er", 0.15)
            et["blended_annual_demand_rate"] = state.get("blended_dr", 10.0)

    # PV
    pv = scn["PV"]
    pv.update(state.get("PV", {}))
    pv.setdefault("installed_cost_per_kw", 1000.0)

    # BESS
    es = scn["ElectricStorage"]
    es.update(state.get("ElectricStorage", {}))
    es.setdefault("installed_cost_per_kwh", 350.0)
    es.setdefault("installed_cost_per_kw", 150.0)
    es.setdefault("soc_min_fraction", 0.1)

    # NG (CHP) and Diesel map straight through if user enabled them in your cards
    if card("CHP"):
        scn["CHP"] = card("CHP")
    if card("Generator"):
        scn["Generator"] = card("Generator")

    # Resilience / ElectricUtility
    eu = {}
    el["critical_load_fraction"] = sget("critical_load_fraction", card("ElectricLoad").get("critical_load_fraction", 1.0))
    start = sget("outage_start_time_step", card("ElectricUtility").get("outage_start_time_step"))
    end = sget("outage_end_time_step", card("ElectricUtility").get("outage_end_time_step"))
    if start and end:
        eu["outage_start_time_step"] = int(start)
        eu["outage_end_time_step"]   = int(end)
    if eu:
        scn["ElectricUtility"] = eu

    # Financials
    fin = scn["Financial"]
    fin["analysis_years"] = sget("analysis_years", 25)
    fin["offtaker_discount_rate_fraction"] = sget("offtaker_discount_rate_fraction", 0.08)
    fin["elec_cost_escalation_rate_fraction"] = sget("elec_cost_escalation_rate_fraction", 0.025)
    fin["itc"] = sget("itc", 0.30)
    fin["macrs_option_years"] = sget("macrs_option_years", 5)
    fin["bonus_depreciation_fraction"] = sget("bonus_depreciation_fraction", 0.0)
    fin["capital_incentive"] = sget("capital_incentive", 0.0)

    # validations
    err = _validate_load(scn)
    if err:
        errors.append(err)
    if not settings["off_grid_flag"] and not _valid_tariff(scn):
        errors.append("ElectricTariff is missing. Choose a URDB rate or enter a blended tariff.")

    return scn, errors


def preflight_checks(state: dict) -> list:
    """
    Quick client-side validation to catch obvious issues before submitting to the backend.
    Returns a list of human-readable error strings (empty if OK).
    Checks:
    - Site.latitude and Site.longitude present and numeric
    - If loads_kw provided, its length matches 8760 * time_steps_per_hour
    """
    errs = []
    # Accept either a built scenario (contains 'Site'/'ElectricLoad') or the raw session_state
    is_built = isinstance(state, dict) and "Site" in state and "ElectricLoad" in state
    if is_built:
        scenario = state
        nested = scenario
    else:
        nested = state.get("scenario") if isinstance(state.get("scenario"), dict) else {}

    def sget(k, default=None):
        # prefer nested scenario values, fall back to top-level state safely
        if isinstance(nested, dict) and k in nested:
            return nested.get(k, default)
        if isinstance(state, dict) and not is_built:
            return state.get(k, default)
        return default

    # site
    # If caller passed a built scenario, Site may live at state['Site']
    if is_built:
        lat = state.get("Site", {}).get("latitude")
        lon = state.get("Site", {}).get("longitude")
    else:
        lat = sget("latitude")
        lon = sget("longitude")
        if lat is None and isinstance(nested, dict):
            lat = nested.get("Site", {}) and nested.get("Site", {}).get("latitude")
        if lon is None and isinstance(nested, dict):
            lon = nested.get("Site", {}) and nested.get("Site", {}).get("longitude")
    if lat is None or lon is None:
        errs.append("Site.latitude and Site.longitude are required.")
    else:
        try:
            float(lat); float(lon)
        except Exception:
            errs.append("Site.latitude and Site.longitude must be numeric.")

    # loads
    el = (nested.get("ElectricLoad") if isinstance(nested, dict) else None) or (state.get("ElectricLoad") if isinstance(state, dict) else None) or {}
    loads = el.get("loads_kw") if isinstance(el, dict) else None
    try:
        tph = int(sget("time_steps_per_hour", 1) or 1)
    except Exception:
        tph = 1
    if loads is not None:
        try:
            if len(loads) != 8760 * tph:
                errs.append(f"ElectricLoad.loads_kw length must be {8760 * tph} (got {len(loads)}).")
        except Exception:
            errs.append("ElectricLoad.loads_kw must be an array-like of numeric values")

    return errs
