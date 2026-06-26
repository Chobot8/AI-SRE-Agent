# AI SRE Agent

An AI Site Reliability Engineering agent that detects, explains, and recommends
actions for common service incidents (high latency, error-rate spikes, pod crash
loops, queue backlogs, database saturation).

This repository currently contains the **service foundation** (KAN-2): a runnable
FastAPI backend with a health endpoint, configuration management, and the project
structure for the features that follow.

## Project structure

```
AI-SRE-Agent/
├── backend/              # FastAPI application
│   ├── main.py           # App entry point (app + root route)
│   ├── config.py         # Settings via pydantic-settings (env-driven)
│   ├── api/routes/       # API route modules
│   │   └── health.py     # GET /health liveness endpoint
│   └── core/             # Shared domain logic & schemas (grows with KAN-5)
├── agent/                # AI workflow: RAG + reasoning (KAN-4, KAN-5, KAN-6)
├── ui/                   # Incident-triage demo UI (KAN-8)
├── infra/                # Dockerfiles, docker-compose, CI assets (KAN-10, KAN-11)
├── docs/                 # Architecture and design docs
├── tests/                # Pytest suite
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Project + tooling config
├── .env.example          # Environment variable template (copy to .env)
└── .gitignore
```

## Prerequisites

- Python 3.11+

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your local environment file
cp .env.example .env        # Windows: copy .env.example .env
```

## Run

```bash
uvicorn backend.main:app --reload
```

Then open:

- Service root: http://localhost:8000/
- Health check: http://localhost:8000/health
- Interactive API docs (OpenAPI): http://localhost:8000/docs

A successful health response looks like:

```json
{
  "status": "ok",
  "service": "AI SRE Agent",
  "version": "0.1.0",
  "environment": "local"
}
```

## Run with Docker (containerized demo stack)

The whole demo (API + UI) runs in containers via docker-compose (KAN-10). This is
the easiest way to demo the project on another machine — only Docker is required.

Prerequisites: Docker Engine with Compose v2 (`docker compose version` ≥ 2.24).

```bash
# From the repo root — build and start the stack
docker compose -f infra/docker-compose.yml up --build
```

This starts two services:

- **api** — FastAPI backend at http://localhost:8000 (`/health`, `/docs`)
- **ui** — Streamlit incident-triage UI at http://localhost:8501

The UI waits for the API to report healthy before starting. Both containers expose
Docker health checks (the API probes `/health`; the UI probes Streamlit's
`/_stcore/health`), so `docker compose ps` shows each service as `healthy`.

Configuration is read from the environment. Defaults work out of the box; to
supply local values or LLM keys, copy `.env.example` to `.env` first (it is
gitignored and loaded automatically — no secrets are committed):

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

Stop the stack with `Ctrl+C`, then clean up with:

```bash
docker compose -f infra/docker-compose.yml down
```

A separate vector-database container is intentionally **not** included: the RAG
index is built in-process from `knowledge/runbooks/`, and the "mock observability
data" is the bundled `sample-data/incidents/` replayed through the API.

## Test

```bash
pytest
```

## Evaluate

KAN-9 adds a deterministic local evaluation baseline in
`sample-data/evaluation/baseline.json`. It covers the five bundled synthetic
incident scenarios and checks expected root cause, relevant evidence, runbook
retrieval quality, and diagnosis completeness.

Run the evaluation checks with:

```bash
pytest tests/test_evaluation.py
```

## Configuration

All configuration is read from environment variables (loaded from `.env` in
development) via `backend/config.py`. See `.env.example` for the full list.
**Never commit real secrets** — `.env` is gitignored; only `.env.example` is tracked.

## Roadmap

This foundation is the basis for the AI SRE Agent backlog (Jira project `KAN`):

| Ticket | Area |
| ------ | ---- |
| KAN-3  | Telemetry ingestion layer (metrics, logs, alerts) |
| KAN-4  | Runbook knowledge base + RAG |
| KAN-5  | Incident analysis & root-cause hypotheses |
| KAN-6  | Remediation recommendations with safety guardrails |
| KAN-7  | Incident diagnosis API endpoints |
| KAN-8  | Incident triage UI |
| KAN-9  | Evaluation dataset & tests |
| KAN-10 | Containerization & docker-compose |
| KAN-11 | CI pipeline |
| KAN-12 | Agent observability (logs, metrics, tracing) |
| KAN-13 | Portfolio README, architecture diagram, demo script |
