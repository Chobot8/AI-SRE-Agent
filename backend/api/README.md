# Incident diagnosis API (KAN-7)

A clean backend interface over the analysis (KAN-5) and remediation (KAN-6)
layers, for demos, tests, and the UI (KAN-8).

## Endpoints

| Method & path | Purpose |
| --- | --- |
| `POST /incidents/diagnose` | Submit a normalized incident; returns a `diagnosis_id`. |
| `POST /incidents/replay/{scenario}` | Replay a bundled sample scenario; returns a `diagnosis_id`. |
| `GET /diagnoses/{diagnosis_id}` | Fetch the full diagnosis: summary, hypotheses, evidence, recommendations. |
| `GET /scenarios` | List supported scenarios and their replay URLs. |
| `GET /health` | Liveness (KAN-2). |

## Request / response

- **Request body** for `POST /incidents/diagnose` is the normalized incident
  schema (KAN-3, `NormalizedIncident`). Invalid payloads return a **422** with
  structured field errors.
- **Submit/replay** return `{ diagnosis_id, incident_id, status }` (HTTP 201).
- **GET /diagnoses/{id}** returns the stored result: the diagnosis
  (`summary`, ranked `hypotheses` with `evidence` + `recommended_checks`) plus
  `remediation` (recommendations with risk, rollback note, and `approval_required`
  flags; `auto_execution: false`).

## Run + explore

```bash
uvicorn backend.main:app --reload
```

- OpenAPI docs: http://localhost:8000/docs
- Quick demo:
  ```bash
  curl -X POST localhost:8000/incidents/replay/db_saturation
  curl localhost:8000/diagnoses/<diagnosis_id>
  curl localhost:8000/scenarios
  ```

## Design

The route handlers are thin wrappers over `backend/api/service.py`
(`DiagnosisService`), which is framework-agnostic and unit-tested without the web
stack (`tests/test_diagnosis_service.py`). Endpoint behaviour is tested with
FastAPI's `TestClient` (`tests/test_api.py`). Results are kept in an in-memory
store for the MVP.
