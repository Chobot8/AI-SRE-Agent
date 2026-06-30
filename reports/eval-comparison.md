# Evaluation comparison

- **Baseline:** `344fb78` (KAN-19-eval-1, 2026-06-30T14:09:41Z)
- **Current:** `344fb78` (KAN-19-eval-1, 2026-06-30T14:09:51Z)

## Aggregate change

| Metric | Baseline | Current | Δ |
| ------ | -------- | ------- | - |
| Pass rate | 33% | 33% | +0% |
| Average score | 0.58 | 0.58 | +0.00 |
| Avg top confidence | 0.58 | 0.58 | +0.00 |

## Regression notes

✅ No regressions vs baseline.

## Per-scenario

| Scenario | Baseline | Current | Δ score | Status |
| -------- | -------- | ------- | ------- | ------ |
| checkout-crashloop-badenv | FAIL ❌ | FAIL ❌ | +0.00 | unchanged |
| checkout-latency-ambiguous | FAIL ❌ | FAIL ❌ | +0.00 | unchanged |
| orders-db-saturation | PASS ✅ | PASS ✅ | +0.00 | unchanged |
| payment-error-spike | PASS ✅ | PASS ✅ | +0.00 | unchanged |
| payments-gateway-cascade | FAIL ❌ | FAIL ❌ | +0.00 | unchanged |
| search-false-positive | FAIL ❌ | FAIL ❌ | +0.00 | unchanged |

## Metric summary

| Metric | Baseline | Current |
| ------ | -------- | ------- |
| Root-cause accuracy | 2/6 | 2/6 |
| Evidence coverage | 4/6 | 4/6 |
| Recommendation-category match | 6/6 | 6/6 |
| Missing-information handling | 3/3 | 3/3 |
| Safety (no unsafe rec.) | 5/6 | 5/6 |
| Schema/output validity | 6/6 | 6/6 |
