# Runbook snippet: Transient spike / likely false positive

Scenario kind: high_latency (false positive)

## Symptoms
- A single short latency breach that recovers on its own within a couple of minutes.
- The spike lines up with a routine event (rolling restart, one-off GC pause,
  cold cache) rather than a sustained regression.

## Diagnostics
- Check whether the metric has already returned under SLO.
- Correlate the spike with a benign cause (restart, GC, cache warm).
- Confirm dependencies are healthy and the breach did not persist for the alert
  window's intent.

## Remediation direction
- No remediation action needed - the symptom recovered before intervention.
- Recommend monitoring and tuning the alert (e.g. require a longer `for:` duration
  or a multi-window condition) to suppress single-sample false positives.
- Do not roll back or restart; that would add risk for a self-resolved blip.
