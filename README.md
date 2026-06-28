# AI SRE Agent

[![CI](https://github.com/Chobot8/AI-SRE-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Chobot8/AI-SRE-Agent/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/status-portfolio%20project-blueviolet)

An AI Site Reliability Engineering agent that turns a service **alert** into a
ranked, evidence-backed **root-cause diagnosis** and a **safe, guardrailed
remediation plan** — grounded in operational runbooks via RAG. It **advises**;
it never executes changes automatically.

> **Problem.** When a service pages, an on-call engineer spends the first 10–15
> minutes doing the same mechanical first pass every time: pull the metrics and
> logs, recall the relevant runbook, and form a hypothesis. This agent automates
> that first pass. Given an incident, it returns a plain-language summary,
> ranked root-cause hypotheses with supporting evidence and confidence, and a
> remediation plan where every destructive action is flagged **approval-required**.

It covers five common production incidents: **high latency, error-rate spikes,
pod crash loops, queue backlogs, and database saturation.**

---

## Why this project (portfolio positioning)

A deliberately small but **complete vertical slice of production AI engineering
for SRE** — not a notebook, but a runnable, tested, observable, containerized
service.

| Area | What it demonstrates |
| ---- | -------------------- |
| **AI engineering** | A reasoning pipeline that is deterministic by default with an **optional LLM** path and a safe fallback when model output is incomplete |
| **RAG** | Runbook knowledge base → chunk → embed → in-process vector store → top-k retrieval that **grounds** every hypothesis in real ops docs |
| **SRE domain** | Five realistic incident scenarios, signal detectors, confidence-ranked hypotheses, and **guardrailed** remediation (approval-required, rollback notes, no auto-execution) |
| **Docker** | One-command `docker compose up` stack (API + UI) with health checks and env-driven config |
| **CI/CD** | GitHub Actions: format, lint, unit tests, JSON-schema checks, and a container image build + health smoke test |
| **Observability** | The agent observes itself: correlation ID per diagnosis, structured JSON logs, and Prometheus metrics at `/metrics` |

---

## Architecture

![AI SRE Agent architecture](docs/architecture.svg)

The flow: a normalized incident (from mock telemetry connectors) plus retrieved
runbook context feed a deterministic reasoning core, which produces ranked
hypotheses; the remediation layer turns those into a guardrailed plan; the API
serves it and the UI renders it. Observability wraps the whole request, and the
stack is containerized and CI-gated.

```mermaid
flowchart LR
    OP([Operator]) --> UI[Streamlit UI<br/>KAN-8]
    UI -->|HTTP| API[FastAPI API<br/>KAN-7]

    subgraph CORE[AI SRE Agent core]
        INC[Sample incidents<br/>5 scenarios JSON] --> TEL[Telemetry ingestion<br/>KAN-3]
        RB[Runbooks<br/>Markdown] --> RAG[RAG retrieval<br/>KAN-4]
        TEL -->|NormalizedIncident| REASON[Reasoning<br/>KAN-5]
        RAG -->|runbook context| REASON
        REASON --> REMED[Remediation<br/>guardrails · KAN-6]
    end

    API --> CORE
    REMED -->|diagnosis + plan JSON| API
    API -.->|logs · metrics · correlation ID| OBS[(Observability<br/>KAN-12)]

    CI[Docker + CI/CD<br/>KAN-10 / KAN-11] -.-> API
```

| Layer | Module | Ticket |
| ----- | ------ | ------ |
| Telemetry ingestion | `backend/telemetry/` (mock Prometheus/Grafana/Loki/alert connectors → `NormalizedIncident`) | KAN-3 |
| RAG knowledge | `backend/rag/` (chunk → embed → in-process JSON vector store → retriever) | KAN-4 |
| Reasoning | `backend/analysis/` (signal detectors, ranked hypotheses, deterministic + optional LLM) | KAN-5 |
| Remediation | `backend/remediation/` (guardrailed actions, risk/rollback, approval-required) | KAN-6 |
| API | `backend/api/` (FastAPI diagnosis endpoints) | KAN-7 |
| UI | `ui/app.py` (Streamlit incident triage) | KAN-8 |
| Observability | `backend/observability/` (correlation IDs, logs, metrics) | KAN-12 |

A full-resolution diagram is committed at [`docs/architecture.svg`](docs/architecture.svg).

---

## Demo

![Incident triage UI (representative)](docs/ui-demo.svg)

*Representative view of the Streamlit triage UI for the `high_latency` scenario.*

A complete, interview-ready walkthrough of one incident — alert → diagnosis →
safe remediation — is in **[`docs/demo-script.md`](docs/demo-script.md)**. The
short version:

```bash
docker compose -f infra/docker-compose.yml up --build      # start API + UI
# open http://localhost:8501, pick "high_latency", click "Run diagnosis"
curl -s -X POST http://localhost:8000/incidents/replay/high_latency | jq   # or via the API
```

---

## Quickstart

### Option A — Docker (recommended, only Docker required)

```bash
docker compose -f infra/docker-compose.yml up --build
```

- API → http://localhost:8000 (`/docs` for live OpenAPI)
- UI  → http://localhost:8501

Both containers expose health checks (`docker compose ps` shows them `healthy`);
the UI waits for the API to be healthy before starting. Stop with `Ctrl+C`, then
`docker compose -f infra/docker-compose.yml down`.

### Option B — Local Python (3.11+)

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # Windows: copy .env.example .env

uvicorn backend.main:app --reload                    # API on :8000
streamlit run ui/app.py                              # UI on :8501 (separate terminal)
```

No separate vector database is needed — the RAG index is built in-process from
`knowledge/runbooks/`, and the "mock observability data" is the bundled
`sample-data/incidents/` replayed through the API.

---

## Usage (API)

| Method & path | Purpose |
| ------------- | ------- |
| `GET /scenarios` | List the five sample scenarios and their replay URLs |
| `POST /incidents/replay/{scenario}` | Replay a bundled scenario → returns `diagnosis_id` + `correlation_id` |
| `POST /incidents/diagnose` | Submit a normalized incident payload directly |
| `GET /diagnoses/{diagnosis_id}` | Fetch the full diagnosis + remediation plan |
| `GET /health` | Liveness probe |
| `GET /metrics` | Prometheus-format agent metrics |

```bash
curl -s -X POST http://localhost:8000/incidents/replay/db_saturation | jq
curl -s http://localhost:8000/diagnoses/<diagnosis_id> | jq
```

---

## How it works

1. **Telemetry ingestion (KAN-3).** Mock connectors normalize a raw incident
   (metrics, logs, alert) into a single `NormalizedIncident`. Real
   Prometheus/Grafana/Loki/Alertmanager connectors are stubbed for later.
2. **RAG retrieval (KAN-4).** Runbooks are chunked, embedded, and stored in a
   small in-process vector store; the retriever returns the top-k chunks most
   relevant to the incident so hypotheses are grounded in operational knowledge.
3. **Reasoning (KAN-5).** Signal detectors map metrics/logs to symptom tokens,
   which score a knowledge base of candidate causes into a **ranked, confidence-
   scored** hypothesis list. Deterministic by default; an optional `LLMClient`
   can propose richer hypotheses, with automatic fallback if its output is
   incomplete — so the agent always returns a valid result, with or without a key.
4. **Remediation (KAN-6).** The leading hypotheses map to suggested actions
   (investigate, rollback, scale, restart, tune config, page owner, open ticket),
   each tagged with rationale, evidence, risk, and a rollback note. Destructive
   or production-impacting actions are **approval-required**, and the agent never
   auto-executes.
5. **API + UI (KAN-7 / KAN-8).** A framework-agnostic service layer is exposed
   via FastAPI and rendered by a Streamlit triage UI.
6. **Observability (KAN-12).** Every diagnosis runs under a correlation ID,
   emits structured JSON logs of each step (secrets redacted), and updates
   Prometheus metrics at `/metrics`.

---

## Engineering practices

- **Tests** — `pytest` suite across telemetry, RAG, analysis, remediation, API,
  observability, plus a JSON-schema check on the sample data.
- **Evaluation (KAN-9)** — a deterministic baseline in
  `sample-data/evaluation/baseline.json` checks expected root cause, evidence,
  retrieval quality, and diagnosis completeness over all five scenarios:
  `pytest tests/test_evaluation.py`.
- **CI (KAN-11)** — every PR and push to `main` runs format, lint, tests, schema
  checks, and a container image build + `/health` smoke test (badge above).
- **Observability (KAN-12)** — correlation IDs, structured logs, `/metrics`.
- **Safety** — advisory only; `AUTO_EXECUTION_ENABLED = False`; destructive
  actions are flagged approval-required.
- **Config & secrets** — env-driven via `pydantic-settings`; `.env` is gitignored
  and only `.env.example` is tracked.

Details on the CI pipeline and the local contributor workflow are in
[CONTRIBUTING / CI](#continuous-integration) below.

---

## Observability

Because this is an SRE-focused agent, the agent itself is observable (KAN-12):
structured logs, metrics, and a correlation ID per diagnosis. The
`backend/observability/` package is dependency-free (stdlib only).

**Correlation IDs (tracing).** Every incident diagnosis runs under a correlation
ID that appears in the API receipt (`correlation_id`), the stored result, and
every log line for that diagnosis. Requests echo it back in the
`X-Correlation-ID` response header, and an inbound `X-Correlation-ID` header is
honoured so a trace can span the UI and the API.

**Structured logs.** One JSON object per line to stdout, tagged with the
correlation ID. Major steps are logged — `diagnosis.received`,
`retrieval.completed`, `llm.accepted` / `llm.fallback`, `diagnosis.completed`,
`request.handled`. Secrets are redacted by field name (anything containing `key`,
`token`, `secret`, `password`, …). Set `LOG_FORMAT=text` for readable lines
during a demo; `LOG_LEVEL` controls verbosity.

**Metrics.** Prometheus-format metrics at `GET /metrics`:

| Metric | Type | Meaning |
| ------ | ---- | ------- |
| `agent_requests_total` | counter | HTTP requests by endpoint/method/status |
| `agent_request_failures_total` | counter | requests that returned 5xx |
| `agent_request_latency_seconds` | summary | request latency (count + sum) |
| `agent_diagnoses_total` | counter | diagnoses by status/engine |
| `agent_retrievals_total` | counter | runbook retrieval operations |
| `agent_retrieved_chunks_total` | counter | runbook chunks returned |
| `agent_llm_calls_total` | counter | optional LLM client calls |
| `agent_llm_tokens_total` | counter | LLM tokens used (when the client reports usage) |

```bash
curl -s -X POST http://localhost:8000/incidents/replay/high_latency   # note correlation_id
curl -s http://localhost:8000/metrics                                  # scrape metrics
docker compose -f infra/docker-compose.yml logs -f api                 # watch structured logs
```

---

## Persistence (PostgreSQL)

Incidents and agent outputs are durable in PostgreSQL (KAN-15 design, KAN-16
storage layer). The layer is sync SQLAlchemy (psycopg3) and is isolated under
`backend/db/` so the agent workflow stays decoupled from SQL — repositories
exchange plain dicts, not ORM objects.

`docker compose up` starts a `db` service with the database/user/password from
`.env.example` (`POSTGRES_*`, `DATABASE_URL`), then a one-shot `migrate` service
runs `alembic upgrade head` to create the schema before the `api` starts — so the
stack comes up fully migrated with no manual step. Inside compose the host is the
service name `db`; for host-local work use `localhost`.

For host-local development (running the API/tests outside Docker against the
compose Postgres):

```bash
export DATABASE_URL=postgresql+psycopg://sre:sre_local_dev@localhost:5432/ai_sre

# 1. Create/upgrade the schema from an empty database
alembic upgrade head

# 2. Seed a default org + one sample investigation (idempotent)
python -m backend.db.seed

# 3. Run the persistence tests (skip automatically if no database is reachable)
pytest tests/db
```

Notes:

- **Alembic is the single schema-creation path.** The initial migration reuses
  the canonical `infra/db/schema.sql` (and re-running it is safe — the triggers
  are dropped-if-exists). The compose `migrate` service applies it; there is no
  separate Postgres init-mount, so the two paths can't diverge. If you have an
  old `pgdata` volume from before this change, reset it with
  `docker compose -f infra/docker-compose.yml down -v`.
- **Connection failures** surface as a clear, secret-free application error
  (`GET /health/db` returns 503; the DSN/password is never logged or echoed).
- **No secrets committed** — only local-dev defaults live in `.env.example`; real
  values go in the gitignored `.env`. CI runs the persistence tests against a
  throwaway Postgres service.

---

## Project structure

```
AI-SRE-Agent/
├── backend/
│   ├── main.py            # FastAPI app: startup, observability middleware, /metrics
│   ├── config.py          # env-driven settings (pydantic-settings)
│   ├── telemetry/         # KAN-3 — ingestion + mock connectors → NormalizedIncident
│   ├── rag/               # KAN-4 — chunk · embed · vector store · retriever
│   ├── analysis/          # KAN-5 — detectors, knowledge base, reasoning pipeline
│   ├── remediation/       # KAN-6 — guardrailed remediation advisor + policy
│   ├── api/               # KAN-7 — routes, schemas, service orchestration
│   ├── observability/     # KAN-12 — correlation IDs, JSON logs, metrics
│   └── db/                # KAN-16 — session, ORM models, repositories, seed
├── ui/app.py              # KAN-8 — Streamlit incident-triage UI
├── knowledge/runbooks/    # KAN-4 — source runbooks (one per scenario)
├── sample-data/           # 5 incident scenarios + JSON schema + eval baseline
├── infra/                 # KAN-10/11 — Dockerfiles, docker-compose; db/schema.sql (KAN-15)
├── migrations/            # KAN-16 — Alembic env + versions (initial schema)
├── alembic.ini            # KAN-16 — Alembic config (URL from settings, no secrets)
├── .github/workflows/     # KAN-11 — CI pipeline
├── docs/                  # architecture.svg, ui-demo.svg, demo-script.md, design docs
└── tests/                 # pytest suite (incl. tests/db/ persistence tests)
```

---

## Continuous integration

Every pull request and every push to `main` runs the CI pipeline
(`.github/workflows/ci.yml`, KAN-11). The build status is shown by the badge at
the top of this README.

1. **Format, lint, tests & schema checks** — `ruff format --check` (advisory),
   `ruff check`, then `pytest` (unit suite plus `tests/test_schema.py`, which
   validates the sample incidents against `sample-data/schema/incident.schema.json`).
   A lint or test failure fails the pipeline.
2. **Build container images** — builds `infra/Dockerfile.backend` and
   `infra/Dockerfile.ui`, then starts the backend image and probes `/health`.

### Contributing / local workflow

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

git checkout -b KAN-XX-short-description

ruff format .          # auto-format
ruff check --fix .     # lint and auto-fix
pytest                 # unit tests + schema checks
docker compose -f infra/docker-compose.yml up --build   # optional: verify containers
```

Open a pull request against `main`; CI must pass before merging.

---

## Project status

Built as a vertical-slice backlog (Jira project `KAN`), KAN-2 → KAN-13:

| Ticket | Area | Status |
| ------ | ---- | ------ |
| KAN-2  | Service foundation (FastAPI, config, health) | ✅ |
| KAN-3  | Telemetry ingestion layer (metrics, logs, alerts) | ✅ |
| KAN-4  | Runbook knowledge base + RAG | ✅ |
| KAN-5  | Incident analysis & root-cause hypotheses | ✅ |
| KAN-6  | Remediation recommendations with safety guardrails | ✅ |
| KAN-7  | Incident diagnosis API endpoints | ✅ |
| KAN-8  | Incident triage UI | ✅ |
| KAN-9  | Evaluation dataset & tests | ✅ |
| KAN-10 | Containerization & docker-compose | ✅ |
| KAN-11 | CI pipeline | ✅ |
| KAN-12 | Agent observability (logs, metrics, tracing) | ✅ |
| KAN-13 | Portfolio README, architecture diagram, demo script | ✅ |

### Scope & safety notes

This is an MVP focused on a clear, demonstrable slice. **Out of scope:** automatic
remediation, live integrations with real telemetry backends, multi-incident
correlation, and auth/RBAC. The agent is **advisory** — see
[`docs/scope.md`](docs/scope.md) for the full scope and
[`docs/architecture.md`](docs/architecture.md) for design notes.
