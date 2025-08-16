import streamlit as st

def show():
    st.header("🛡️ Resilience Settings")

    st.checkbox("Resilience Mode (Backup Power)", key="resilience_mode")
    if st.session_state.get("resilience_mode"):
        st.number_input(
            "Critical Load Fraction (0-1)",
            min_value=0.0,
            max_value=1.0,
            value=st.session_state.get("critical_load_fraction", 0.5),
            key="critical_load_fraction",
        )
        # keep both outage duration (hours) and editable start/end time steps
        hours = st.number_input(
            "Outage Duration (hours)",
            min_value=0,
            value=st.session_state.get("outage_hours", 24),
            key="outage_hours",
        )
        # Convert outage hours into end time step relative to start=0 for simple UX
        try:
            tph = int(st.session_state.get("time_steps_per_hour", 1) or 1)
            st.session_state["outage_start_time_step"] = 0
            st.session_state["outage_end_time_step"] = int(hours * tph)
        except Exception:
            pass
