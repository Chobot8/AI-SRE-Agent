# Runbook: High latency / p99 SLO breach

Scenario: high_latency

## Symptoms

- Request latency (p95/p99) breaches the service SLO while error rate stays low.
- Latency rises gradually rather than spiking instantly.
- Throughput (requests per second) is roughly flat, so this is not a traffic surge.

## Likely causes

- A slow downstream dependency (database, cache, or external API).
- An expensive or unindexed database query (e.g. missing index, full table scan).
- Connection-pool or thread-pool contention causing requests to queue.
- Recently shipped code path that added latency.

## Diagnostics

- Compare request latency against downstream dependency latency on the same time range; if they rise together, the dependency is the bottleneck.
- Confirm throughput is flat to rule out a load-driven cause.
- Check slow-query logs for the affected datastore; look for missing indexes.
- Inspect connection-pool wait/acquire time.

## Remediation

- If a slow query is the cause: add the missing index or optimize the query; consider a short-term query timeout to shed load.
- If a downstream dependency is saturated: scale it or add caching for hot reads.
- If pool contention: increase pool size cautiously and add backpressure.
- Investigate first; none of these are auto-applied. Index changes are low risk; scaling is medium risk.

## Escalation / references

- Page the service owner if p99 stays above SLO for more than 15 minutes.
- Related: db_saturation runbook when the dependency is the primary database.
