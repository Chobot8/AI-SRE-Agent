# Runbook snippet: Error-rate spike after deploy

Scenario kind: error_rate_spike

## Symptoms
- 5xx ratio jumps well above baseline within minutes.
- The jump aligns closely with a recent deployment or config change.
- A specific exception repeats in logs (e.g. NullPointerException).

## Diagnostics
- Correlate error onset with the deploy marker / release timeline.
- Confirm request rate is flat (rules out a traffic surge).
- Identify the dominant exception signature and the code path it hits.

## Remediation direction
- If the spike began right after a deploy: roll back to the previous known-good
  version. It is the fastest reversible mitigation.
- Rollback is production-impacting and should be approval-gated.
- Capture the failing version and a sample stack trace for the post-incident review.
