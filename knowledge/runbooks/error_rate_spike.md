# Runbook: Error-rate spike (5xx surge)

Scenario: error_rate_spike

## Symptoms

- 5xx error ratio jumps well above its normal baseline within minutes.
- The jump often aligns closely with a recent deployment or config change.
- Specific exceptions repeat in logs (e.g. NullPointerException, unhandled errors).

## Likely causes

- A regression in a newly deployed release (bad release).
- A breaking change in a downstream API contract or response shape.
- A bad configuration or feature-flag change pushed to production.

## Diagnostics

- Correlate the error onset with the deploy marker / release timeline.
- Identify the dominant exception or error signature in logs.
- Check whether the errors are concentrated in one code path or endpoint.

## Remediation

- If the spike began right after a deploy: roll back to the previous known-good version. This is the fastest mitigation and is reversible.
- If a config/flag change caused it: revert the change.
- Rollback is production-impacting and should be approval-gated, but is the standard first response to a release regression.

## Escalation / references

- Page the on-call owner immediately for a critical error-rate breach.
- Capture the failing version and a sample stack trace for the post-incident review.
