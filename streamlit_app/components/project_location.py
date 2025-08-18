import streamlit as st


def show():
    scn = st.session_state.setdefault("scenario", {})
    site = scn.setdefault("Site", {})
    settings = scn.setdefault("Settings", {"time_steps_per_hour": 1, "off_grid_flag": False})

    st.subheader("📍 Project & Location")
    site["name"] = st.text_input("Project name", value=site.get("name", "My Site"), key="site_name")

    c1, c2 = st.columns(2)
    with c1:
        site["latitude"] = st.number_input("Latitude", value=site.get("latitude", 34.05), format="%.6f", key="site_lat")
    with c2:
        site["longitude"] = st.number_input("Longitude", value=site.get("longitude", -118.25), format="%.6f", key="site_lon")

    settings["time_steps_per_hour"] = st.number_input(
        "Time steps per hour",
        value=settings.get("time_steps_per_hour", 1),
        min_value=1,
        step=1,
        key="settings_tph",
    )

    # Allow entering a ZIP code which we'll convert to lat/lon behind the scenes
    zip_code = st.text_input("ZIP code (optional)", value=site.get("zip", ""), key="site_zip")
    if zip_code:
        zip_map = {
            "80302": (40.0150, -105.2705),  # Boulder, CO
            "94103": (37.7726, -122.4090),  # San Francisco, CA
            "20001": (38.9101, -77.0147),   # Washington, DC
            "10001": (40.7506, -73.9972),   # New York, NY
            "90210": (34.0888, -118.4061),  # Beverly Hills, CA
        }
        z = zip_code.strip()
        if z in zip_map:
            lat, lon = zip_map[z]
            site["latitude"] = lat
            site["longitude"] = lon
            site["zip"] = z
            st.info(f"Resolved ZIP {z} → lat={lat:.4f}, lon={lon:.4f}")
        else:
            # don't overwrite existing lat/lon if unknown ZIP
            st.caption("ZIP not in local mapping; enter lat/lon manually if needed.")
