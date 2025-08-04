# Vortx Opt2 REopt MVP

This repository contains a minimal example of connecting to NREL's REopt v3 API.
It includes:

- **Flask backend** for submitting REopt scenarios and polling results.
- **React frontend** for editing a scenario and viewing outputs.

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
python app.py
```

Set your API key in `backend/.env`:

```
NREL_API_KEY=YOUR_REAL_NREL_KEY
```

### Frontend

```bash
cd frontend
npm install
npm start
```

With both services running, open your browser at `http://localhost:3000` to try the app.
