# Runbook snippet: Pod CrashLoopBackOff

Scenario kind: pod_crash_loop

## Symptoms
- Pods restart repeatedly; ready replicas drop toward zero.
- kubelet reports `CrashLoopBackOff` for the container.

## Differentiate the cause
- **Config/secret error:** the process exits non-zero during init with a clear
  config/validation message; memory is well below the limit.
- **OOMKilled:** the last state termination reason is `OOMKilled` and memory
  rides the limit before each restart.

## Diagnostics
- Read the container's first log lines after each restart (the real error is at startup).
- Check whether a required env var / mounted secret is present and non-empty.
- Confirm the working-set memory is not near the limit (rules out OOM).

## Remediation direction
- For a missing/invalid secret or env var: restore the correct value (or roll back
  the manifest/config change that dropped it) and redeploy.
- This is a configuration fix; coordinate the secret change with the owning team.
