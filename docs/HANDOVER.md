# Handover Notes

_AI SRE Agent — handover for the next engineer/agent._

## Current State

- **Milestone / version:** `0.1.0` (see `pyproject.toml`). MVP feature set
  complete: telemetry ingestion → RAG → reasoning → remediation → API → UI, with
  observability, containers, CI, and a PostgreSQL persistence layer.
- **Completed Jira range:** KAN-2 → KAN-13 (core build, all merged to `main`),
  KAN-15 (persistence model/design, merged), KAN-16 (PostgreSQL storage layer,
  **Done**). KAN-14 was a throwaway workflow probe, not a feature.
- **Current branch expectations:** `main` contains everything through KAN-15.
  KAN-16 lives on branch **`KAN-16-postgres-storage-layer`** (commits `e24d9c3`,
  `87304bc`, `d19af12`) and **still needs to be pushed and merged** —
  `git push -u origin KAN-16-postgres-storage-layer`, then open/merge the PR.
  New work branches off `main` as `KAN-<n>-short-description`.

## Start Here

Read these first, in order:

1. **`README.md`** — what the agent does, architecture, quickstart, usage, and
   the engineering story (also embeds the architecture diagram).
2. **`docs/data-model.md`** — the persistence model, entity relationships,
   investigation lifecycle, and the redaction/secret policy.
3. **`docs/demo-script.md`** — a 3–5 min end-to-end incident walkthrough
   (alert → diagnosis → safe remediation) for demos/interviews.
4. **`AGENTS.md`** — repo conventions, setup/verification commands, and the
   KAN ticket workflow.

Also useful: `docs/architecture.md` (+ `architecture.svg`) and the per-package
READMEs under `backend/*/`.

## Run The App

```bash
# From the repo root — build and start the whole stack
docker compose -f infra/docker-compose.yml up --build
```

Expected services (defined in `infra/docker-compose.yml`):

- **db** — `postgres:16-alpine`, data in the named volume `pgdata`.
- **migrate** — one-shot; runs `alembic upgrade head`, then exits.
- **api** — FastAPI backend on http://localhost:8000 (`/docs` for OpenAPI).
- **ui** — Streamlit incident-triage UI on http://localhost:8501.

Startup order: `db` (healthy) → `migrate` (completes) → `api` (healthy) → `ui`.

Health checks:

- **db** — `pg_isready` (compose healthcheck).
- **api** — `GET /health` (liveness) and `GET /health/db` (DB readiness).
- **ui** — Streamlit `/_stcore/health`.
- `docker compose -f infra/docker-compose.yml ps` should show each long-running
  service as `healthy` and `migrate` as exited 0.

## Database Workflow

- **Compose DB service:** `db` (`postgres:16-alpine`); credentials/db name from
  `.env.example` (`POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB`),
  persisted in volume `pgdata`. There is **no** `/docker-entrypoint-initdb.d/`
  schema mount.
- **Alembic migration path (single source of truth):** the `migrate` service
  runs `alembic upgrade head`. The initial migration
  (`migrations/versions/0001_initial_schema.py`) executes the canonical
  `infra/db/schema.sql`; `downgrade` drops the `sre` schema. Run it manually for
  host-local dev with `alembic upgrade head`.
- **`DATABASE_URL` notes:** SQLAlchemy URL using psycopg3. Inside compose the
  host is the service name **`db`**
  (`postgresql+psycopg://sre:sre_local_dev@db:5432/ai_sre`); for host-local runs
  (API/tests outside Docker) use **`localhost`**. Default lives in
  `infra/docker-compose.yml` and `.env.example`; never commit real secrets.
- **Seed command:** `python -m backend.db.seed` — creates a default org and one
  sample investigation (idempotent).
- **DB test command:** `pytest tests/db` — requires `DATABASE_URL` set and a
  reachable Postgres; the tests **skip cleanly** when no DB is available.

## Verification Checklist

```bash
# Lint (blocking gate)
ruff check .

# Full test suite (unit + schema checks; DB tests need a reachable Postgres)
pytest

# Validate the compose stack renders
docker compose -f infra/docker-compose.yml config

# Probes (stack running)
curl -s http://localhost:8000/health      # liveness
curl -s http://localhost:8000/health/db   # DB readiness (503 if DB down)
curl -s http://localhost:8000/metrics     # Prometheus metrics
```

CI (`.github/workflows/ci.yml`) runs ruff format (advisory), `ruff check`,
`alembic upgrade head` against a throwaway Postgres service, and `pytest` — then
builds the container images.

## Known Caveats

- **Ruff format is advisory**, not blocking. The blocking lint gate is
  `ruff check` (rules `E`, `F`, `W`); import sorting (`I`) and formatting are
  handled by `ruff format` / `ruff check --fix` locally, not enforced in CI.
- **Use PowerShell for the Windows venv DB tests** (activate with
  `.venv\Scripts\Activate.ps1`, then `pytest tests/db`), and set `DATABASE_URL`
  to the `localhost` form.
- **Reset an old `pgdata` volume after migration-path changes:**
  `docker compose -f infra/docker-compose.yml down -v` (a volume created by the
  earlier init-mount approach has the schema but no `alembic_version` row).

## Next Follow-Ups

- **SQLAlchemy integration into the API/service flow** — the storage layer
  exists (`backend/db/`) but the live diagnosis path (`backend/api/service.py`)
  still uses the in-memory store; wire repositories in behind it.
- **Persist live diagnosis results** — on each diagnosis, write the incident,
  agent run, evidence, retrieved chunks, diagnosis, hypotheses, and
  recommendations via `InvestigationRepository.create_full`.
- **Evaluation persistence** — record `evaluation_runs` / `evaluation_results`
  from the KAN-9 baseline so regression history is queryable.
