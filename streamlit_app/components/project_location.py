import streamlit as st

def show():
    st.header("📍 Project Location")
    st.text_input("Site Name", key="site_name", value=st.session_state.get("site_name", ""))
    st.text_input(
        "Address or Coordinates (enter 'lat, lon' or a 5-digit US ZIP)",
        key="site_location",
        value=st.session_state.get("site_location", ""),
        help="Examples: '40.0150, -105.2705' or '80302' (ZIP). If you provide a ZIP code we'll attempt to resolve it to coordinates for quick testing."
    )
