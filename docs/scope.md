# AI SRE Agent — MVP Scope (KAN-1)

## MVP goal

Build an AI Site Reliability Engineering agent that, given the context of a
service incident, can **detect, explain, and recommend actions** — turning raw
telemetry and an alert into a readable diagnosis with ranked root-cause
hypotheses and safe remediation suggestions. The agent **advises**; it never
executes changes automatically in the MVP.

## Target incident scenarios

The MVP focuses on five common, well-understood production incidents. Each has a
matching sample dataset under `sample-data/incidents/`.

| # | Scenario | Typical signal | Example root cause |
| - | -------- | -------------- | ------------------ |
| 1 | High latency | p99 latency breaches SLO | Slow downstream dependency / DB query |
| 2 | Error-rate spike | 5xx rate jumps after a deploy | Bad release / regression |
| 3 | Pod crash loop | Pod restarts repeatedly (CrashLoopBackOff) | OOMKilled / failing readiness probe |
| 4 | Queue backlog | Consumer lag grows unbounded | Stuck/slow consumer, throughput < ingest |
| 5 | Database saturation | Connections/CPU at capacity | Connection pool exhaustion / lock contention |

## User flow (alert → diagnosis → remediation)

1. **Alert intake** — an alert payload arrives (or a stored scenario is replayed).
2. **Context collection** — the agent gathers related metrics, logs, and any
   matching runbook snippets (RAG) for the affected service.
3. **Symptom synthesis** — it summarizes what is happening and the key evidence.
4. **Root-cause hypotheses** — it produces a ranked list of likely causes, each
   with supporting evidence, a confidence level, and the next diagnostic check.
5. **Remediation recommendations** — for the leading hypotheses it suggests
   actions (investigate, rollback, scale, restart, tune config, page owner, open
   follow-up ticket), each tagged with rationale, evidence, risk, and a rollback
   note. Destructive/production-impacting actions are flagged **approval-required**.
6. **Output** — the result is returned as machine-readable JSON for the API/UI.

## Out of scope (MVP)

- **Automatic remediation / auto-execution** of any change. Recommendations only.
- **Live integrations** with real Prometheus/Grafana/Loki/PagerDuty — the MVP uses
  mock/sample data (real connectors are stubbed for KAN-3 to extend later).
- **Multi-incident correlation** and long-term trend analysis.
- **Authentication, multi-tenancy, RBAC**, and production-grade security hardening.
- **Alert routing / on-call scheduling** — the agent consumes alerts, it doesn't manage them.
- Scenarios beyond the five listed above (e.g. network partitions, cert expiry, DNS).

## Demo success criteria

The first demo is successful if, for at least one scenario end to end:

- A sample alert is submitted/replayed and the agent returns a diagnosis.
- The diagnosis contains a plain-language **summary**, **supporting evidence**
  (specific metrics/logs), and **ranked root-cause hypotheses** with confidence.
- At least one **remediation recommendation** is shown with rationale, risk level,
  and rollback note, and any destructive action is clearly **approval-required**.
- The output is viewable both as JSON (API) and in a readable form (UI, KAN-8).
- The flow is reproducible from the sample data with no manual data prep.

## Notes

Derived from the AI SRE Agent project scope (Jira KAN-1). The five scenarios and
their sample datasets are the working basis for the telemetry layer (KAN-3),
runbook RAG (KAN-4), reasoning workflow (KAN-5), and evaluation set (KAN-9).
