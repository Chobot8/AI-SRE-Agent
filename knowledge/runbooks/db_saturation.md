# Runbook: Database saturation

Scenario: db_saturation

## Symptoms

- Database connection pool is exhausted (in-use connections at the max).
- Database CPU is near capacity and lock-wait events spike.
- Dependent services report "could not get connection from pool" errors.

## Likely causes

- Lock contention from a long-running transaction holding a row/table lock.
- Connection-pool exhaustion from slow queries holding connections open.
- A traffic or query-pattern change overwhelming the primary instance.

## Diagnostics

- Identify long-running transactions and the locks they hold.
- Plot in-use connections against the pool maximum and CPU utilization.
- Check for downstream "pool exhausted" errors that confirm saturation.

## Remediation

- Terminate or commit the blocking long-running transaction to release locks.
- Add statement/lock timeouts so transactions cannot hold locks indefinitely.
- Add read replicas or scale the instance if the cause is sustained load.
- Killing a transaction is medium-to-high risk and is production-impacting: approval-required before execution.

## Escalation / references

- Page the database owner for a critical saturation event.
- Related: high_latency runbook, since DB saturation commonly surfaces first as upstream latency.
