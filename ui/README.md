# UI

Minimal Streamlit incident-triage demo for KAN-8. It lets a user select a bundled
sample incident, replay it through the backend API, and review the diagnosis,
evidence, root-cause hypotheses, and remediation recommendations.

## Run

From the repo root, install dependencies first:

```bash
pip install -r requirements.txt
```

Start the backend API:

```bash
uvicorn backend.main:app --reload
```

In another terminal, start the UI:

```bash
streamlit run ui/app.py
```

The UI defaults to `http://localhost:8000`. Change the backend URL in the
sidebar if the API is running elsewhere.

## Expected Flow

1. The UI loads scenarios from `GET /scenarios`.
2. Clicking **Run diagnosis** calls `POST /incidents/replay/{scenario}`.
3. The UI fetches the full result from `GET /diagnoses/{diagnosis_id}`.
4. Output is grouped into summary, evidence, hypotheses, recommendations, and raw JSON.
