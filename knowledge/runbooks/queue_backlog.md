# Runbook: Queue backlog / consumer lag

Scenario: queue_backlog

## Symptoms

- Consumer lag (unprocessed messages) grows steadily and does not recover.
- Consume rate collapses while the produce/ingest rate stays steady.
- Worker logs show timeouts or all workers blocked on a downstream call.

## Likely causes

- A stuck or slow consumer blocked on an unresponsive downstream (e.g. SMTP, an API, a database).
- Throughput permanently below ingest rate (under-provisioned consumers).
- Poison messages causing repeated retries that stall the worker pool.

## Diagnostics

- Compare consume rate vs produce rate; a steady produce rate with collapsed consume rate points to a stuck consumer.
- Check worker logs for downstream timeouts or blocked worker pools.
- Look for a single message being retried repeatedly (poison message).

## Remediation

- Restore or fail over the unresponsive downstream dependency.
- Shorten downstream timeouts and add a dead-letter queue so poison messages don't block the pool.
- Scale out consumers once the blocking dependency is healthy to drain the backlog.
- Draining is low risk; changing timeout/DLQ behaviour is medium risk and should be reviewed.

## Escalation / references

- Escalate if backlog threatens data freshness SLAs or storage limits.
- Related: high_latency / db_saturation runbooks when the blocking downstream is a database.
