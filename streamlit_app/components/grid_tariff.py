import streamlit as st

def show():
    st.header("⚡ Grid & Tariff")

    connection_options = ["Grid-Connected", "Off-Grid"]
    st.radio(
        "Connection Type",
        connection_options,
        index=connection_options.index(
            st.session_state.get("grid_connection", "Grid-Connected")
        ),
        key="grid_connection",
    )

    if st.session_state.get("grid_connection") == "Grid-Connected":
        st.text_input("Utility", key="utility_name", value=st.session_state.get("utility_name", ""))
        st.text_input("Tariff Name", key="tariff_name", value=st.session_state.get("tariff_name", ""))
        st.number_input("Blended Energy Rate ($/kWh)", min_value=0.0, value=st.session_state.get("blended_er", 0.15), key="blended_er")
        st.number_input("Demand Charge ($/kW)", min_value=0.0, value=st.session_state.get("blended_dr", 20.0), key="blended_dr")
        st.number_input("Fixed Monthly Charge ($)", min_value=0.0, value=st.session_state.get("fixed_monthly_charge", 50.0), key="fixed_monthly_charge")
    else:
        st.info("Running in off-grid mode — tariff inputs are ignored.")
