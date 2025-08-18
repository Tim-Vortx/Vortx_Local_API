import streamlit as st
import pandas as pd
import math


def _make_synthetic_profile(base: float, peak: float, time_steps_per_hour: int = 1, year: int = 2024):
    hours_per_year = 8760
    total_steps = hours_per_year * int(time_steps_per_hour)
    profile = [0.0] * total_steps
    for step in range(total_steps):
        hour = (step / time_steps_per_hour) % 24
        x = math.cos((hour - 16) / 24.0 * 2 * math.pi)
        amp = max(0.0, peak - base)
        val = base + (0.5 * (1 + x)) * amp
        profile[step] = val
    return profile


def show():
    scn = st.session_state.setdefault("scenario", {})
    el = scn.setdefault("ElectricLoad", {})
    settings = scn.setdefault("Settings", {"time_steps_per_hour": 1})

    st.subheader("📊 Load Builder")

    method = st.radio("Load input method", ["Synthetic (peak + load factor)", "Upload 8760 CSV"], horizontal=True, key="load_method")

    # Ensure we always have values for peak/load_factor (persisted in scenario)
    peak_kw = el.get("peak_kw", 300.0)
    load_factor = el.get("load_factor", 0.25)

    if method == "Synthetic (peak + load factor)":
        # remove uploaded loads if present
        el.pop("loads_kw", None)
        c1, c2 = st.columns(2)
        with c1:
            peak_kw = st.number_input("Peak load (kW)", value=peak_kw, min_value=0.0, key="peak_kw")
        with c2:
            load_factor = st.number_input("Load factor (0..1)", value=load_factor, min_value=0.0, max_value=1.0, step=0.01, key="load_factor")

    tph = int(settings.get("time_steps_per_hour", 1))
    # expose year input so user can change it before generating
    year = st.number_input("Load Year", value=el.get("year", 2024), key="load_year", step=1)

    # persist the numeric inputs immediately so changing them updates the scenario
    el["peak_kw"] = peak_kw
    el["load_factor"] = load_factor

    if st.button("Generate synthetic 8760", key="gen_synth"):
        with st.spinner("Generating synthetic profile..."):
            # aim: produce a profile whose average = peak * load_factor while keeping
            # the profile peak equal to the requested peak when possible.
            tph_i = int(tph)
            desired_avg = float(peak_kw) * float(load_factor)

            # For our waveform the mean of the shape factor (0.5*(1+cos)) is 0.5.
            avg_x = 0.5

            # Solve for base so that avg = base + avg_x*(peak-base) => base = peak*(2*lf - 1)
            base_candidate = float(peak_kw) * (2.0 * float(load_factor) - 1.0)

            if base_candidate >= 0.0:
                base = base_candidate
                used_peak = float(peak_kw)
                amp = used_peak - base
            else:
                # Can't set negative base. Set base=0 and reduce the generated peak so
                # avg = avg_x * generated_peak => generated_peak = desired_avg / avg_x
                base = 0.0
                used_peak = desired_avg / avg_x if avg_x > 0 else float(peak_kw)
                amp = used_peak - base

            # build waveform with base and amp so peak == used_peak
            raw_profile = _make_synthetic_profile(base=base, peak=used_peak, time_steps_per_hour=tph_i, year=year)

            # no additional scaling required: waveform constructed to match desired average
            profile = raw_profile

            el["loads_kw"] = profile
            el["year"] = year
            # keep user's requested peak in the scenario but show actual generated peak
            el["peak_kw"] = peak_kw
            el["load_factor"] = load_factor
            generated_peak = max(profile) if profile else 0.0
            st.success(f"Generated profile ({len(profile)} points). Saved to scenario → ElectricLoad.loads_kw")
            if abs(generated_peak - float(peak_kw)) > 1e-6:
                st.info(f"Generated profile peak = {generated_peak:.1f} kW (requested {float(peak_kw):.1f} kW). To achieve the requested load factor with a non-negative base the peak was adjusted.")
            else:
                st.info(f"Generated profile peak = {generated_peak:.1f} kW (matches requested peak)")

            steps_per_day = 24 * tph_i
            if len(profile) >= steps_per_day:
                day0 = profile[:steps_per_day]
                times = [f"{int(i/tph_i):02d}:00" for i in range(steps_per_day)]
                df_day = pd.DataFrame({"kW": day0}, index=times)
                st.markdown("**Sample: single-day load curve**")
                st.line_chart(df_day)
    else:
        file = st.file_uploader("Upload 8760 hourly kW CSV with column 'kW'", type=["csv"], key="load_csv")
        if file is not None:
            # pandas can read Streamlit's UploadedFile
            df = pd.read_csv(file)
            rows = int(df.shape[0])
            if "kW" in df.columns and rows in (8760, 8784):
                loads = df["kW"].iloc[:8760].tolist()
                el["loads_kw"] = loads
                el["year"] = st.number_input("Load Year", value=el.get("year", 2024), key="load_year", step=1)
                st.line_chart(df["kW"].iloc[:168], height=120)
            else:
                st.error("CSV must have a 'kW' column with 8760 rows.")

