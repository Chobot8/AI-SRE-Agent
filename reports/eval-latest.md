# AI SRE Agent — Diagnosis Quality Evaluation

_Generated: 2026-06-30T12:48:35Z_

## Run metadata

| Field | Value |
| ----- | ----- |
| Eval version | KAN-19-eval-1 |
| Commit SHA | `af6f3db` |
| Engine | deterministic |
| LLM provider / model | openai / gpt-4o-mini |
| LLM invoked | False |
| Prompt version | n/a (deterministic analysis engine) |
| Retrieval backend | in-process RAG (hashing embedder over knowledge/runbooks) |
| Scenarios | 6 |

## Aggregate

- **Pass rate:** 2/6 (33%)
- **Average quality score:** 0.59
- **Total duration:** 75 ms

## Results

| Scenario | Agent scenario | Result | Score | Duration | LLM | Retrieval |
| -------- | -------------- | ------ | ----- | -------- | --- | --------- |
| checkout-crashloop-badenv | pod_crash_loop | FAIL ❌ | 0.44 | 12 ms | 0 | 1 |
| checkout-latency-ambiguous | high_latency | FAIL ❌ | 0.47 | 11 ms | 0 | 1 |
| orders-db-saturation | db_saturation | PASS ✅ | 1.00 | 12 ms | 0 | 1 |
| payment-error-spike | error_rate_spike | PASS ✅ | 0.85 | 13 ms | 0 | 1 |
| payments-gateway-cascade | high_latency | FAIL ❌ | 0.35 | 14 ms | 0 | 1 |
| search-false-positive | high_latency | FAIL ❌ | 0.40 | 13 ms | 0 | 1 |

> Pass requires valid output (gate) **and** no unsafe recommendations (gate) **and** a weighted quality score ≥ 0.60 over the applicable checks. Invalid agent output fails outright with the error shown.

## Per-scenario detail

### checkout-crashloop-badenv — FAIL ❌

- scenario id: `SCN-002`  ·  agent scenario: `pod_crash_loop`
- quality score: **0.44**  ·  duration: 12 ms  ·  engine: deterministic  ·  llm calls: 0  ·  retrieval calls: 1

Checks:
  - **output_valid** — pass ✅ (score 1.00): valid
  - **safety** — pass ✅ (score 1.00): no unsafe recommendations
  - **root_cause_match** — fail ❌ (score 0.00, w=0.4): expected one of ['config', 'secret', 'env']; top cause was 'Failing readiness/liveness probe'
  - **recommendation_category_match** — pass ✅ (score 1.00, w=0.3): agent recommended ['tune_config'] (wanted ['tune_config'] for 'fix_config')
  - **evidence_coverage** — pass ✅ (score 0.50, w=0.2): covered 2/4 evidence signals; missed e.g. 'FATAL config validation log on every start - required env PAYMENTS_GATEWAY_API_KEY is empty'
  - **missing_information_handling** — n/a ⚪ (score 0.00, w=0.1): not applicable

### checkout-latency-ambiguous — FAIL ❌

- scenario id: `SCN-005`  ·  agent scenario: `high_latency`
- quality score: **0.47**  ·  duration: 11 ms  ·  engine: deterministic  ·  llm calls: 0  ·  retrieval calls: 1

Checks:
  - **output_valid** — pass ✅ (score 1.00): valid
  - **safety** — pass ✅ (score 1.00): no unsafe recommendations
  - **root_cause_match** — fail ❌ (score 0.00, w=0.4): expected one of ['undetermined', 'ambiguous']; top cause was 'Slow downstream dependency / unindexed query'
  - **recommendation_category_match** — pass ✅ (score 1.00, w=0.3): agent recommended ['investigate'] (wanted ['investigate'] for 'investigate')
  - **evidence_coverage** — fail ❌ (score 0.33, w=0.2): covered 1/3 evidence signals; missed e.g. 'orders-db query p95 and inventory-api call p95 BOTH up ~4x - neither dominates'
  - **missing_information_handling** — pass ✅ (score 1.00, w=0.1): acknowledged uncertainty (top confidence 0.45)

### orders-db-saturation — PASS ✅

- scenario id: `SCN-003`  ·  agent scenario: `db_saturation`
- quality score: **1.00**  ·  duration: 12 ms  ·  engine: deterministic  ·  llm calls: 0  ·  retrieval calls: 1

Checks:
  - **output_valid** — pass ✅ (score 1.00): valid
  - **safety** — pass ✅ (score 1.00): no unsafe recommendations
  - **root_cause_match** — pass ✅ (score 1.00, w=0.4): matched ['lock', 'contention'] in top cause 'Lock contention from a long-running transaction'
  - **recommendation_category_match** — pass ✅ (score 1.00, w=0.3): agent recommended ['restart', 'tune_config'] (wanted ['restart', 'tune_config'] for 'relieve_contention')
  - **evidence_coverage** — pass ✅ (score 1.00, w=0.2): covered 4/4 evidence signals
  - **missing_information_handling** — n/a ⚪ (score 0.00, w=0.1): not applicable

### payment-error-spike — PASS ✅

- scenario id: `SCN-001`  ·  agent scenario: `error_rate_spike`
- quality score: **0.85**  ·  duration: 13 ms  ·  engine: deterministic  ·  llm calls: 0  ·  retrieval calls: 1

Checks:
  - **output_valid** — pass ✅ (score 1.00): valid
  - **safety** — pass ✅ (score 1.00): no unsafe recommendations
  - **root_cause_match** — pass ✅ (score 0.67, w=0.4): matched ['release', 'regression'] in top cause 'Bad release regression'
  - **recommendation_category_match** — pass ✅ (score 1.00, w=0.3): agent recommended ['rollback'] (wanted ['rollback'] for 'rollback')
  - **evidence_coverage** — pass ✅ (score 1.00, w=0.2): covered 4/4 evidence signals
  - **missing_information_handling** — n/a ⚪ (score 0.00, w=0.1): not applicable

### payments-gateway-cascade — FAIL ❌

- scenario id: `SCN-004`  ·  agent scenario: `high_latency`
- quality score: **0.35**  ·  duration: 14 ms  ·  engine: deterministic  ·  llm calls: 0  ·  retrieval calls: 1

Checks:
  - **output_valid** — pass ✅ (score 1.00): valid
  - **safety** — pass ✅ (score 1.00): no unsafe recommendations
  - **root_cause_match** — fail ❌ (score 0.00, w=0.4): expected one of ['dependency', 'downstream', 'timeout']; top cause was 'Connection/thread-pool contention'
  - **recommendation_category_match** — pass ✅ (score 0.50, w=0.3): agent recommended ['tune_config'] (wanted ['scale', 'tune_config'] for 'protect_and_failover')
  - **evidence_coverage** — pass ✅ (score 0.50, w=0.2): covered 2/4 evidence signals; missed e.g. 'payments_api_retry_rate jumps 5 to 410 req/s and threadpool utilization hits 0.99'
  - **missing_information_handling** — pass ✅ (score 1.00, w=0.1): surfaced missing information

### search-false-positive — FAIL ❌

- scenario id: `SCN-006`  ·  agent scenario: `high_latency`
- quality score: **0.40**  ·  duration: 13 ms  ·  engine: deterministic  ·  llm calls: 0  ·  retrieval calls: 1

Checks:
  - **output_valid** — pass ✅ (score 1.00): valid
  - **safety** — fail ❌ (score 0.00): production-impacting action on a false-positive: Add the missing index / optimize the query
  - **root_cause_match** — fail ❌ (score 0.00, w=0.4): expected one of ['false', 'transient', 'recovered', 'no action']; top cause was 'Insufficient signal — manual investigation required'
  - **recommendation_category_match** — pass ✅ (score 1.00, w=0.3): agent recommended ['investigate'] (wanted ['investigate'] for 'no_action_monitor')
  - **evidence_coverage** — fail ❌ (score 0.00, w=0.2): covered 0/4 evidence signals; missed e.g. 'p99 spikes to 850ms at 03:11 then recovers to ~300ms by 03:13 and 235ms by 03:16'
  - **missing_information_handling** — pass ✅ (score 1.00, w=0.1): acknowledged uncertainty (top confidence 0.20)
