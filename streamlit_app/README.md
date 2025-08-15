Streamlit REopt Frontend

Files:
- `app.py` — Streamlit app to select or upload a scenario, run REopt, and display results
- `requirements.txt` — Python dependencies
- `../scripts/run_reopt.jl` — Julia wrapper script invoked by the Streamlit app

Run locally:
1. Install Python deps:

```bash
pip install -r streamlit_app/requirements.txt
```

2. From the repo root, run Streamlit:

```bash
streamlit run streamlit_app/app.py
```

The app will call Julia using the `julia` command; ensure Julia is installed and the `julia` binary is on your PATH.
