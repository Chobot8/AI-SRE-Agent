# Repository Instructions

## Setup And Verification
- Python 3.11+ project; install dependencies with `pip install -r requirements.txt` after activating a local venv.
- Run the backend with `uvicorn backend.main:app --reload`; config is loaded from environment variables and optional `.env` via `backend/config.py`.
- Primary verification is `pytest`; focused runs work as `pytest tests/test_api.py` or `pytest tests/test_rag.py::test_retrieval_returns_relevant_runbook`.
- Ruff is configured in `pyproject.toml` for Python 3.11 and 100-character lines, but no ruff dependency or script is currently declared.

## Architecture Notes
- `backend/main.py` is the FastAPI entrypoint. Route modules under `backend/api/routes/` only become live if explicitly included there.
- `backend/api/service.py` is framework-agnostic orchestration for diagnosis + remediation and uses an in-memory result store for the MVP.
- `backend/telemetry/` normalizes sample incidents; default/mock ingestion reads `sample-data/incidents/*.json` and writes generated output under gitignored `data/`.
- `backend/rag/` builds a deterministic local runbook index from `knowledge/runbooks/*.md`; generated indexes under `data/rag/` are derived and gitignored.
- `backend/analysis/` is deterministic by default and can fall back from optional LLM output to rule/template-based diagnosis.
- `backend/remediation/` is advisory only: `AUTO_EXECUTION_ENABLED = False`, and `execute()` must not perform production actions.
- `ui/` and `infra/` are placeholders; do not assume a runnable frontend or Docker/CI flow exists yet.

## Useful Local Commands
- `python -m backend.telemetry` ingests all sample scenarios; add a scenario name such as `high_latency` to ingest one.
- `python -m backend.rag build` rebuilds the runbook index; `python -m backend.rag incident high_latency` tests incident retrieval.
- `python -m backend.analysis db_saturation --json` runs a machine-readable diagnosis for a sample incident.
- `python -m backend.remediation error_rate_spike --json` runs diagnosis followed by guardrailed recommendations.

## OpenCode / KAN Workflow
- `opencode.jsonc` imports `CLAUDE.md`, which says to use `.opencode/skills/kan-ticket-to-review` after completing any `KAN-**` ticket.
- For KAN work, keep scope tied to the ticket, update or add pytest coverage for behavior changes, and do not commit unless explicitly asked.
