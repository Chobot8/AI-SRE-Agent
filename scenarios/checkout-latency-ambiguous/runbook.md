# Runbook snippet: High latency with an unclear bottleneck

Scenario kind: high_latency (ambiguous)

## Symptoms
- p95 latency is over SLO while request rate is flat.
- Two downstream paths (a database query and an internal dependency) are *both*
  elevated by a similar factor, and no single one clearly dominates.

## Why it is ambiguous
- Without per-request tracing you cannot attribute the latency budget to the DB
  query vs the inventory-api call - either could be the bottleneck, or both.

## Diagnostics
- Re-enable distributed tracing sampling (even briefly) to attribute the latency
  budget per span.
- EXPLAIN the suspect orders query to confirm/deny a missing index.
- Check inventory-api's own latency source independently.

## Remediation direction
- Investigate first - gather tracing/EXPLAIN before making a change.
- Do not roll back or re-index blindly; collect the disambiguating signal, then
  act on whichever path actually owns the latency budget.
