# Runbook: Pod crash loop (CrashLoopBackOff)

Scenario: pod_crash_loop

## Symptoms

- A pod restarts repeatedly; Kubernetes reports CrashLoopBackOff.
- Restart count climbs quickly over a few minutes.
- Container memory usage hits its limit just before each restart (when OOM-related).

## Likely causes

- OOMKilled: the container exceeds its memory limit (e.g. loading a large dataset at startup).
- A failing readiness/liveness probe restarting an otherwise-healthy container.
- A crash on startup due to a bad config, missing secret, or failed migration.

## Diagnostics

- Read the last container termination reason (OOMKilled vs Error vs probe failure).
- Plot container memory against its limit around the restart times.
- Inspect startup logs for the action immediately preceding the crash.

## Remediation

- If OOMKilled: raise the memory limit, or reduce startup memory (stream/lazy-load large data instead of loading it all at once).
- If probe-driven: relax probe thresholds or fix the slow startup path.
- If config/migration: fix the config or roll back the change.
- Memory-limit changes are low-to-medium risk; validate the new limit against actual usage.

## Escalation / references

- If the crash loop affects a stateful or singleton workload, escalate to the service owner promptly.
- Related: high_latency runbook if the restart loop degrades dependent services.
