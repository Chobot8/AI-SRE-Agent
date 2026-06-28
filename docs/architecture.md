# Architecture

High-level architecture of the AI SRE Agent. The committed diagram is
[`architecture.svg`](./architecture.svg) (a Mermaid version is embedded in the
[README](../README.md#architecture)).

![AI SRE Agent architecture](./architecture.svg)

## Component overview

A normalized incident (from mock telemetry connectors) plus retrieved runbook
context feed a deterministic reasoning core, which produces ranked hypotheses;
the remediation layer turns those into a guardrailed plan; the API serves it and
the UI renders it. Observability wraps the whole request, and the stack is
containerized and CI-gated.

| Layer | Module | Ticket | Responsibility |
| ----- | ------ | ------ | -------------- |
| Telemetry ingestion | `backend/telemetry/` | KAN-3 | Normalize raw metrics/logs/alerts (mock Prometheus/Grafana/Loki/alert connectors) into a `NormalizedIncident` |
| RAG knowledge | `backend/rag/` | KAN-4 | Chunk + embed runbooks into an in-process vector store; retrieve top-k relevant chunks |
| Reasoning | `backend/analysis/` | KAN-5 | Signal detectors → ranked, confidence-scored root-cause hypotheses (deterministic + optional LLM) |
| Remediation | `backend/remediation/` | KAN-6 | Map hypotheses to guardrailed actions (risk, rollback, approval-required) |
| API | `backend/api/` | KAN-7 | FastAPI diagnosis endpoints over a framework-agnostic service layer |
| UI | `ui/app.py` | KAN-8 | Streamlit incident-triage view |
| Observability | `backend/observability/` | KAN-12 | Correlation IDs, structured logs, Prometheus metrics |
| Infra & CI | `infra/`, `.github/workflows/` | KAN-10 / KAN-11 | Docker Compose stack + GitHub Actions pipeline |

## Design principles

- Vertical slices per incident scenario rather than broad horizontal builds.
- Recommendations are grounded in retrieved operational knowledge (RAG), not raw
  model output alone.
- Deterministic by default: the agent returns a valid diagnosis with no model or
  API key; an optional LLM enriches it, with a safe fallback.
- Safety first: the MVP never executes remediation automatically; destructive
  actions are flagged approval-required (KAN-6).
- The agent is itself observable, since this is an SRE-focused project (KAN-12).

## Out of scope (MVP)

Automatic remediation, live integrations with real telemetry backends,
multi-incident correlation, and auth/RBAC. See [`scope.md`](./scope.md) for the
full MVP scope and the five target incident scenarios.
