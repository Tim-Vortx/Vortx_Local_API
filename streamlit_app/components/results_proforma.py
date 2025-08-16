import streamlit as st
import pandas as pd
import io

def show():
    st.header("📒 Proforma")

    results = st.session_state.get("results")
    if not results:
        st.info("Run a scenario to see results.")
        return

    rows = results.get("Financial", {}).get("proforma_rows")
    if not rows:
        st.warning("No proforma rows provided by backend. Populate `Financial.proforma_rows` server-side.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

    buf = io.StringIO()
    df.to_csv(buf, index=False)
    st.download_button("Download CSV", data=buf.getvalue(), file_name="proforma.csv", mime="text/csv")
