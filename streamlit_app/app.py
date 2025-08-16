import streamlit as st
import subprocess
import json
import tempfile
from pathlib import Path
import os

repo_root = Path(__file__).resolve().parent.parent
scenarios_dir = repo_root / "test" / "scenarios"

st.title("REopt Model Runner (Streamlit)")

st.markdown("This app lets you pick a scenario JSON from the repo or upload one, run REopt (Julia) and view results.")

# list scenarios
scenario_files = []
if scenarios_dir.exists():
    scenario_files = sorted([p.relative_to(repo_root) for p in scenarios_dir.glob("*.json")])

choice = st.selectbox("Choose scenario (or upload)", ["(upload)"] + [str(p) for p in scenario_files])

uploaded = None
if choice == "(upload)":
    uploaded = st.file_uploader("Upload scenario JSON", type="json")

selected_path = None
if uploaded is not None:
    tmpdir = tempfile.mkdtemp()
    selected_path = Path(tmpdir) / "uploaded_scenario.json"
    with open(selected_path, "wb") as f:
        import streamlit as st
        import subprocess
        import json
        import tempfile
        from pathlib import Path
        import os

        repo_root = Path(__file__).resolve().parent.parent
        scenarios_dir = repo_root / "test" / "scenarios"

        st.title("REopt Model Runner (Streamlit)")

        st.markdown("This app lets you pick a scenario JSON from the repo or upload one, run REopt (Julia) and view results.")

        # list scenarios
        scenario_files = []
        if scenarios_dir.exists():
            scenario_files = sorted([p.relative_to(repo_root) for p in scenarios_dir.glob("*.json")])

        choice = st.selectbox("Choose scenario (or upload)", ["(upload)"] + [str(p) for p in scenario_files])

        uploaded = None
        if choice == "(upload)":
            uploaded = st.file_uploader("Upload scenario JSON", type="json")

        selected_path = None
        if uploaded is not None:
            tmpdir = tempfile.mkdtemp()
            selected_path = Path(tmpdir) / "uploaded_scenario.json"
            with open(selected_path, "wb") as f:
                f.write(uploaded.getbuffer())
        else:
            if choice != "(upload)":
                selected_path = repo_root / choice

        st.write("Selected:", selected_path)

        solver = st.selectbox("Solver", ["HiGHS", "GLPK"], index=0)

        run_button = st.button("Run REopt")

        if run_button:
            if not selected_path or not selected_path.exists():
                st.error("No scenario selected or uploaded.")
            else:
                out_path = repo_root / "streamlit_results.json"
                cmd = [
                    "julia",
                    f"--project={str(repo_root)}",
                    str(repo_root / "scripts" / "run_reopt.jl"),
                    str(selected_path),
                    str(out_path),
                    solver,
                ]
                st.write("Running:", " ".join(cmd))
                with st.spinner("Running REopt (this may take a while)..."):
                    proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.returncode == 0 and out_path.exists():
                    st.success("Model run complete — results saved to streamlit_results.json")
                    with open(out_path) as f:
                        results = json.load(f)
                    # show basic summary and full json
                    st.header("Summary")
                    if "Financial" in results:
                        fin = results["Financial"]
                        st.metric("LCC", fin.get("lcc", "n/a"))
                        st.metric("Year 1 Energy Cost", fin.get("year_one_energy_cost_before_tax", "n/a"))
                    st.header("Full Results (JSON)")
                    st.json(results)

                    # Download button
                    st.download_button("Download results JSON", data=json.dumps(results), file_name="results.json", mime="application/json")
                else:
                    st.error("Model run failed; check stdout/stderr below.")
                    st.subheader("stdout")
                    st.text(proc.stdout)
                    st.subheader("stderr")
                    st.text(proc.stderr)
