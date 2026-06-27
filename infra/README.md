# Infra

Containerization and deployment assets for the AI SRE Agent.

## Contents (KAN-10)

- `Dockerfile.backend` — FastAPI backend (API) image. Builds the RAG index
  in-process from `knowledge/runbooks/` and serves the health + diagnosis
  endpoints with `uvicorn`.
- `Dockerfile.ui` — Streamlit incident-triage UI image. A thin HTTP client of
  the API.
- `docker-compose.yml` — local demo stack wiring `api` + `ui` together with
  health checks and dependency ordering.

CI workflow definitions (KAN-11) will live here later.

## Run the local demo stack

From the **repo root**:

```bash
docker compose -f infra/docker-compose.yml up --build
```

- API:  http://localhost:8000 (`/health`, `/docs`)
- UI:   http://localhost:8501

The `ui` service starts only after `api` reports healthy (`depends_on:
condition: service_healthy`). Tear down with:

```bash
docker compose -f infra/docker-compose.yml down
```

## Health checks

Both services define container-level health checks so `docker compose ps`
reports their status:

- **api** — probes `GET /health` (FastAPI liveness endpoint).
- **ui**  — probes `GET /_stcore/health` (Streamlit's built-in endpoint).

## Configuration

All configuration is externalized through environment variables — see
`.env.example` at the repo root. Compose loads an optional `.env` (gitignored)
automatically; defaults are sufficient to start the stack. **No secrets are
committed.**

Key variables:

| Variable          | Service | Purpose                                        |
| ----------------- | ------- | ---------------------------------------------- |
| `HOST` / `PORT`   | api     | uvicorn bind address / port                    |
| `APP_NAME`        | api     | Service name surfaced by `/health`             |
| `ENVIRONMENT`     | api     | Environment label (`local`, etc.)              |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | api | Optional LLM keys (blank by default) |
| `BACKEND_API_URL` | ui      | API base URL the UI calls (`http://api:8000`)  |

## Scope notes

The ticket mentions optional containers for a vector database and mock
observability data. Neither is a separate service here, by design:

- **Vector database** — the RAG store (`backend/rag/`) is an in-process,
  JSON-backed index rebuilt from the source runbooks at runtime. There is no
  external database to run.
- **Mock observability data** — the bundled `sample-data/incidents/*.json`
  scenarios are baked into the API image and replayed via the `/scenarios` and
  `/incidents/replay/{scenario}` endpoints.

If a real external vector DB or telemetry backend is introduced later, add it as
an additional compose service and point the backend at it through environment
variables (e.g. `VECTOR_STORE_URL`).
