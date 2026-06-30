# Runbook snippet: Database saturation

Scenario kind: db_saturation

## Symptoms
- Application p99 latency climbs while request rate is roughly flat.
- DB active connections sit at the pool maximum; queries queue.
- Lock-wait time rises; queries fail with lock-wait timeouts.

## Diagnostics
- Find the blocking transaction (longest-running / oldest active pid).
- Check what it is locking and which service or job started it.
- Confirm the connection pool is exhausted rather than the DB being down.

## Remediation direction
- Identify and terminate the blocking long-running transaction to release locks.
- Coordinate with the owning job/service before killing it; work may need a retry.
- Follow up with statement/lock timeouts so one transaction cannot hold locks indefinitely.
