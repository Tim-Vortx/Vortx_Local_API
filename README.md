# Vortx Opt2 REopt MVP

This repository contains a minimal example of connecting to NREL's REopt v3 API.
It includes:

- **Flask backend** for submitting REopt scenarios and polling results.
- **React frontend** for editing a scenario and viewing outputs.

## Quick Start

### Backend

1. Create `backend/.env` containing a valid NREL API key:

   ```
   NREL_API_KEY=YOUR_REAL_NREL_KEY
   ```

2. Install requirements and start Flask on port 5000 (matching the React proxy):

   ```bash
   cd backend
   pip install -r requirements.txt
   python app.py
   ```

### Frontend

The React dev server proxies API calls to the Flask backend. Install dependencies
and start it with:

```bash
cd frontend
npm install
npm start
```

With both services running, open your browser at `http://localhost:3000` to try the app.
