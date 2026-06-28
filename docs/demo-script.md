# Demo Script — AI SRE Agent

A short, repeatable walkthrough for interviews and portfolio reviews. It takes a
single incident end to end — **alert → diagnosis → safe remediation** — and shows
the engineering underneath (RAG, deterministic reasoning, containers, CI,
observability). Target length: **3–5 minutes**.

> Scenario used throughout: `high_latency` on the `checkout-api` service
> (`INC-1001`). Swap in any of the five scenarios — `error_rate_spike`,
> `pod_crash_loop`, `queue_backlog`, `db_saturation` — for variety.

---

## 0. Before you start (30s setup)

```bash
# From the repo root — one command brings up API + UI
docker compose -f infra/docker-compose.yml up --build
```

- API → http://localhost:8000  (`/docs` for live OpenAPI)
- UI  → http://localhost:8501

> No local Python needed — only Docker. `docker compose ps` should show both
> services as `healthy`.

---

## 1. The problem (30s — say this out loud)

> "When a service pages at 2am, an on-call engineer burns the first 15 minutes
> doing the same thing every time: pulling metrics and logs, recalling the right
> runbook, and forming a hypothesis. This agent does that first pass
> automatically. Given an alert, it returns a ranked root-cause diagnosis with
> evidence and a *safe*, guardrailed remediation plan — it advises, it never
> executes."

---

## 2. Run one diagnosis in the UI (60s)

1. Open the UI at http://localhost:8501.
2. In the sidebar the backend URL is pre-filled.
3. Pick **`high_latency`** from the scenario dropdown and click **Run diagnosis**.
4. Walk through the result top to bottom:
   - **Incident Summary** — plain-language: *CRITICAL alert on `checkout-api`,
     p99 1200ms over the 500ms SLO; leading hypothesis: slow downstream /
     unindexed query.*
   - **Evidence** — the specific signals that support it (rising DB query time,
     flat throughput, slow-query log lines).
   - **Root-Cause Hypotheses** — ranked, each with a confidence label and the
     next diagnostic check.
   - **Remediation Recommendations** — each tagged with risk, rationale, a
     rollback note, and **approval-required** on anything destructive.

> Talking point: *"Notice the leading hypothesis is grounded in the runbook via
> RAG, and the destructive action is flagged approval-required — safety is built
> into the model output, not bolted on."*

See [`ui-demo.svg`](./ui-demo.svg) for a reference of this screen.

---

## 3. Same flow via the API (45s — show it's a real service)

```bash
# Replay the scenario; note the diagnosis_id AND correlation_id in the receipt
curl -s -X POST http://localhost:8000/incidents/replay/high_latency | jq

# Fetch the full structured diagnosis
curl -s http://localhost:8000/diagnoses/<diagnosis_id> | jq
```

> Talking point: *"The UI is just a client. The agent is a JSON API, so it can
> drop into a real incident pipeline — an alert webhook, a Slack bot, a PagerDuty
> action."*

---

## 4. Show the agent observing itself (45s — the SRE angle)

```bash
# Every diagnosis carries a correlation ID for tracing
curl -si -X POST http://localhost:8000/incidents/replay/high_latency | grep -i x-correlation-id

# Prometheus-format metrics: requests, latency, diagnoses, retrievals, LLM calls
curl -s http://localhost:8000/metrics | grep agent_

# Structured JSON logs of each workflow step (secrets redacted)
docker compose -f infra/docker-compose.yml logs api | tail -n 20
```

> Talking point: *"Because it's an SRE tool, the agent is itself observable —
> correlation IDs, structured logs, and Prometheus metrics. Secrets are redacted
> from logs by design."*

---

## 5. The engineering story (30s — close on positioning)

> "End to end this is: a **RAG** knowledge layer over runbooks, a **deterministic
> reasoning** core with an optional LLM and safe fallback, a **FastAPI** service,
> a **Streamlit** UI, full **observability**, all **containerized** and gated by a
> **CI pipeline** that lints, tests, validates the data schema, and builds the
> images. It's a small but complete slice of production AI engineering for SRE."

---

## One-liner (for a CV bullet or portfolio caption)

> *AI SRE agent that turns an alert into a ranked, runbook-grounded (RAG)
> root-cause diagnosis and a guardrailed remediation plan — FastAPI + Streamlit,
> fully observable (correlation IDs, logs, Prometheus metrics), containerized,
> and CI-tested.*

---

## Capturing a GIF / screenshots (optional, for the README)

The repo ships `docs/ui-demo.svg` as a reference of the result screen. To capture
a real recording from a live run:

1. Start the stack (`docker compose -f infra/docker-compose.yml up --build`).
2. Record the browser window while running step 2 above with a screen recorder
   (e.g. macOS `Cmd+Shift+5`, [Peek] on Linux, or [ScreenToGif] on Windows).
3. Save it to `docs/screenshots/demo.gif` and reference it from the README.
