import streamlit as st


def show():
    scn = st.session_state.setdefault("scenario", {})
    st.subheader("🔋 DER Selection & Sizing")

    # PV
    pv_on = st.checkbox("Include Solar PV", value=bool(scn.get("PV")), key="pv_on")
    if pv_on:
        pv = scn.setdefault("PV", {})
        pv.setdefault("design_mode", pv.get("design_mode", "optimal"))
        mode = st.radio("PV design mode", ["Optimal", "Prescribed"], index=0 if pv.get("design_mode", "optimal") == "optimal" else 1, key="pv_design_mode")
        pv["design_mode"] = "optimal" if mode == "Optimal" else "prescribed"
        if pv["design_mode"] == "optimal":
            pv["max_kw"] = st.number_input("PV max allowed (kW)", value=pv.get("max_kw", 1000.0), step=10.0, key="pv_max_kw")
        else:
            pv["installed_kw"] = st.number_input("PV installed size (kW)", value=pv.get("installed_kw", 0.0), step=1.0, key="pv_installed_kw")
        pv["installed_cost_per_kw"] = st.number_input("PV installed cost ($/kW)", value=pv.get("installed_cost_per_kw", 1000.0), step=25.0, key="pv_cost")
    else:
        scn.pop("PV", None)

    # BESS
    es_on = st.checkbox("Include Battery Storage", value=bool(scn.get("ElectricStorage")), key="es_on")
    if es_on:
        es = scn.setdefault("ElectricStorage", {})
        es.setdefault("design_mode", es.get("design_mode", "optimal"))
        mode = st.radio("BESS design mode", ["Optimal", "Prescribed"], index=0 if es.get("design_mode", "optimal") == "optimal" else 1, key="es_design_mode")
        es["design_mode"] = "optimal" if mode == "Optimal" else "prescribed"
        if es["design_mode"] == "optimal":
            es["max_kwh"] = st.number_input("BESS max energy allowed (kWh)", value=es.get("max_kwh", 1000.0), step=10.0, key="es_max_kwh")
            es["max_kw"] = st.number_input("BESS max power allowed (kW)", value=es.get("max_kw", 250.0), step=1.0, key="es_max_kw")
        else:
            es["installed_kwh"] = st.number_input("BESS installed energy (kWh)", value=es.get("installed_kwh", 0.0), step=1.0, key="es_installed_kwh")
            es["installed_kw"] = st.number_input("BESS installed power (kW)", value=es.get("installed_kw", 0.0), step=1.0, key="es_installed_kw")
        es["installed_cost_per_kwh"] = st.number_input("BESS cost ($/kWh)", value=es.get("installed_cost_per_kwh", 350.0), step=10.0, key="es_ckwh")
        es["installed_cost_per_kw"] = st.number_input("BESS power cost ($/kW)", value=es.get("installed_cost_per_kw", 150.0), step=10.0, key="es_ckw")
        es["soc_min_fraction"] = st.number_input("Min SOC fraction", value=es.get("soc_min_fraction", 0.1), step=0.05, min_value=0.0, max_value=0.9, key="es_socmin")
        es["model_degradation"] = st.checkbox("Model degradation", value=es.get("model_degradation", False), key="es_degrad")
    else:
        scn.pop("ElectricStorage", None)

    # NG via CHP
    ng_on = st.checkbox("Include Natural Gas (as CHP)", value=bool(scn.get("CHP")), key="ng_on")
    if ng_on:
        chp = scn.setdefault("CHP", {})
        chp["prime_mover"] = "recip_engine"
        chp["fuel_type"] = "natural_gas"
        chp["max_kw"] = st.number_input("NG/CHP max kW", value=chp.get("max_kw", 0), step=50, key="chp_max")
        chp["fuel_cost_per_mmbtu"] = st.number_input("NG fuel cost ($/MMBtu)", value=chp.get("fuel_cost_per_mmbtu", 6.0), step=0.25, key="chp_fuel")
        chp["electric_efficiency_full_load"] = st.number_input("Electrical efficiency (full load)", value=chp.get("electric_efficiency_full_load", 0.38), step=0.01, key="chp_eff")
        chp["min_turn_down_fraction"] = st.number_input("Min turn-down fraction", value=chp.get("min_turn_down_fraction", 0.2), step=0.05, key="chp_turndown")
    else:
        scn.pop("CHP", None)

    # Diesel
    d_on = st.checkbox("Include Diesel Generator", value=bool(scn.get("Generator")), key="diesel_on")
    if d_on:
        gen = scn.setdefault("Generator", {})
        gen["max_kw"] = st.number_input("Diesel max kW", value=gen.get("max_kw", 0), step=50, key="gen_max")
        gen["fuel_cost_per_gallon"] = st.number_input("Diesel fuel cost ($/gal)", value=gen.get("fuel_cost_per_gallon", 4.0), step=0.1, key="gen_fuel")
        gen["electric_efficiency_full_load"] = st.number_input("Electrical efficiency (full load)", value=gen.get("electric_efficiency_full_load", 0.33), step=0.01, key="gen_eff")
        gen["min_turn_down_fraction"] = st.number_input("Min turn-down fraction", value=gen.get("min_turn_down_fraction", 0.15), step=0.05, key="gen_turndown")
        gen["only_runs_during_grid_outage"] = st.checkbox("Only runs during outage", value=gen.get("only_runs_during_grid_outage", False), key="gen_outageonly")
    else:
        scn.pop("Generator", None)
