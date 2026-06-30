# Runbook snippet: External dependency timeout and cascading latency

Scenario kind: high_latency (external dependency)

## Symptoms
- p99 latency climbs sharply; outbound calls to an external dependency time out.
- Internal retries and blocked worker threads amplify the problem and spread it
  to upstream callers (cascade).

## Diagnostics
- Confirm the latency originates at the external dependency (its call latency and
  timeout ratio spike first).
- Check whether retries and thread-pool saturation are amplifying the impact.
- Check the vendor status page for a confirmed incident.

## Remediation direction
- Protect the service: trip a circuit breaker / shed load to the failing
  dependency so retries stop saturating the worker pool.
- Fail fast (shorter timeout, fewer retries, fallback path) while the dependency
  recovers, and engage the vendor.
- Note this is often multi-cause: the external outage is the trigger, but missing
  circuit-breaking / aggressive retries make it worse and are independently fixable.
