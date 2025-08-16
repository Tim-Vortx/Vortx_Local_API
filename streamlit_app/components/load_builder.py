import streamlit as st
import pandas as pd
import math
from datetime import datetime


def _make_synthetic_profile(base: float, peak: float, time_steps_per_hour: int = 1, year: int = 2024):
    """Create a simple diurnal sinusoidal 8760*ts_per_hour profile.
    Returns a list of floats length 8760 * time_steps_per_hour.
    """
    hours_per_year = 8760
    total_steps = hours_per_year * int(time_steps_per_hour)
    profile = [0.0] * total_steps

    # Daily sinusoid: low at 4am, high at 16:00 (4pm)
    for step in range(total_steps):
        # convert step to hour of day
        hour = (step / time_steps_per_hour) % 24
        # value between -1 and 1
        x = math.cos((hour - 16) / 24.0 * 2 * math.pi)
        # scale to base..peak
        amp = max(0.0, peak - base)
        val = base + (0.5 * (1 + x)) * amp
        profile[step] = val

    return profile


def show():
    st.header("📊 Load Builder")

    st.write("Upload or generate a load profile for the site.")

    uploaded_file = st.file_uploader("Upload CSV with hourly load (kW)", type="csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        # If df has a single column of values, show it plainly
        try:
            st.line_chart(df)
        except Exception:
            st.write(df.head())

    st.markdown("---")
    st.write("Or create a synthetic profile:")
    base_load = st.number_input("Base Load (kW)", min_value=0.0, value=100.0, key="base_load_kw")
    peak_load = st.number_input("Peak Load (kW)", min_value=0.0, value=300.0, key="peak_load_kw")

    # Respect Settings.time_steps_per_hour if the UI has it
    tph = 1
    try:
        tph = int(st.session_state.get("scenario", {}).get("Settings", {}).get("time_steps_per_hour", 1))
    except Exception:
        tph = 1

    year = st.session_state.get("scenario", {}).get("Site", {}).get("year", 2024)

    if st.button("Generate Profile"):
        with st.spinner("Generating 8760-hour profile..."):
            profile = _make_synthetic_profile(base_load, peak_load, time_steps_per_hour=tph, year=year)

        # save into session_state scenario so Run panel picks it up
        sc = st.session_state.setdefault("scenario", {})
        sc.setdefault("ElectricLoad", {})
        sc["ElectricLoad"]["loads_kw"] = profile
        sc["ElectricLoad"]["time_steps_per_hour"] = tph
        sc["ElectricLoad"]["year"] = year

        st.success(f"Generated profile ({len(profile)} points). Saved to scenario → ElectricLoad.loads_kw")

        # Show a single-day plot (first full day)
        steps_per_day = 24 * tph
        if len(profile) >= steps_per_day:
            day0 = profile[:steps_per_day]
            # create an index label for a single day to show nicer x-axis
            times = [f"{int(i/tph):02d}:00" for i in range(steps_per_day)]
            df_day = pd.DataFrame({"kW": day0}, index=times)
            st.markdown("**Sample: single-day load curve**")
            st.line_chart(df_day)
        else:
            st.write("Profile too short to show a single day sample.")
