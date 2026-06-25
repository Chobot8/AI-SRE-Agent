# Architecture (working draft)

This document captures the intended high-level architecture. It will be expanded
with a committed diagram in KAN-13.

## Component overview

```
                ┌─────────────────────────────────────────────┐
                │                  UI (KAN-8)                   │
                │        incident selector + result view        │
                └───────────────────────┬─────────────────────┘
                                        │ HTTP
                ┌───────────────────────▼─────────────────────┐
                │             FastAPI backend (KAN-2)           │
                │   /health  •  /  •  diagnosis API (KAN-7)     │
                └───┬───────────────┬───────────────────┬──────┘
                    │               │                   │
          ┌─────────▼──────┐ ┌──────▼────────┐ ┌────────▼─────────┐
          │ Telemetry layer │ │  Agent (RAG + │ │  Observability   │
          │   (KAN-3)       │ │  reasoning)   │ │   (KAN-12)       │
          │ metrics/logs/   │ │ KAN-4, KAN-5, │ │ logs/metrics/    │
          │ alerts (mock)   │ │ KAN-6         │ │ tracing          │
          └─────────────────┘ └──────┬────────┘ └──────────────────┘
                                     │
                            ┌────────▼────────┐
                            │  Vector store    │
                            │  (runbooks, RAG) │
                            └──────────────────┘
```

## Current state (KAN-2)

- **Backend**: FastAPI app (`backend/main.py`) exposing a service root (`/`) and a
  liveness endpoint (`/health`).
- **Config**: environment-driven settings via `pydantic-settings`
  (`backend/config.py`); secrets stay in an untracked `.env`.
- **Structure**: dedicated packages reserved for the AI workflow (`agent/`),
  telemetry, UI, infra, and docs so later tickets slot in cleanly.

## Design principles

- Vertical slices per incident scenario rather than broad horizontal builds.
- Recommendations are grounded in retrieved operational knowledge (RAG), not raw
  model output alone.
- Safety first: the MVP never executes remediation automatically; destructive
  actions are flagged approval-required (KAN-6).
- The agent is itself observable, since this is an SRE-focused project (KAN-12).
