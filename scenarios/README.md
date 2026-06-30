# Incident scenario packs (KAN-18)

Richer, repeatable incident scenarios for realistic agent testing, demos, and
automated evaluation. Everything here is **synthetic** — no real data or secrets.

These complement the single-file samples in `sample-data/incidents/`: each pack
here is a *folder* that adds service-health/dependency status, separate log and
metric files, a runbook snippet, and machine-readable ground truth.

## Domain

Ecommerce / payments microservices (`checkout-api`, `payments-api`, `orders-api`,
`orders-db`, the external `payments-gateway`, `search-api`), matching the services
already used elsewhere in the repo. All data is pure local mock — there is no
dependency on a running service. (Running one scenario against a real
docker-compose failure is noted as a possible future extension.)

## Pack layout

```text
scenarios/
  <slug>/
    alert.json           # inbound alert + service metadata (id, service, environment, severity, ...)
    logs.jsonl           # one JSON log object per line
    metrics.json         # { "metrics": [ { name, unit, description?, points:[{t,value}] } ] }
    service_health.json  # service + dependency status snapshot
    runbook.md           # relevant runbook snippet
    expected.yaml        # machine-readable ground truth (root cause, evidence, remediation, ambiguity)
  schema/                # JSON Schemas the loader validates each file against
```

## The packs

| Slug | Agent scenario | Notes |
| ---- | -------------- | ----- |
| `payment-error-spike` | error_rate_spike | 5xx spike right after a deploy (clear, single cause) |
| `checkout-crashloop-badenv` | pod_crash_loop | CrashLoopBackOff from a missing secret (not OOM) |
| `orders-db-saturation` | db_saturation | Lock contention + pool exhaustion from a batch job |
| `payments-gateway-cascade` | high_latency | **Multi-cause:** external timeout + retry amplification |
| `checkout-latency-ambiguous` | high_latency | **Ambiguous:** DB query vs dependency, no tracing |
| `search-false-positive` | high_latency | **False positive:** transient spike recovers before action |

At least two packs are intentionally ambiguous or multi-cause
(`payments-gateway-cascade`, `checkout-latency-ambiguous`), plus a false-positive
case that exercises the agent's "no action needed" path.

## Replay scenarios locally

The loader (`backend.scenarios`) discovers, validates, and replays packs. It
needs the project dependencies installed (`pip install -r requirements.txt`).

```bash
# List the packs (with ambiguous / multi-cause / false-positive tags)
python -m backend.scenarios list

# Validate file presence + schema for every pack (used by CI/tests)
python -m backend.scenarios validate

# Print the assembled NormalizedIncident the agent consumes
python -m backend.scenarios show payment-error-spike

# Run a pack through the agent locally (no server/DB needed) and compare
# the agent's hypotheses/actions against the expected ground truth
python -m backend.scenarios replay payments-gateway-cascade
```

Each pack also assembles into the canonical `NormalizedIncident` shape
(`sample-data/schema/incident.schema.json`), so it can be POSTed to the API:

```bash
python -m backend.scenarios show orders-db-saturation > /tmp/incident.json
curl -s -X POST http://localhost:8000/incidents \
  -H 'content-type: application/json' -d @/tmp/incident.json | jq
```

## Validation

`tests/test_scenarios.py` enforces the acceptance criteria: ≥5 packs, ≥2
ambiguous/multi-cause, machine-readable expected outputs, required files present,
and that every pack passes schema validation and assembles into a schema-valid
incident. Run it with:

```bash
pytest tests/test_scenarios.py
```

## `expected.yaml` fields

- `agent_scenario` — maps the pack to one of the agent's five reasoning scenarios.
- `is_ambiguous` / `is_multi_cause` / `is_false_positive` — scenario flags.
- `root_cause` — `summary`, `category`, `confidence`.
- `expected_evidence` — the signals a good diagnosis should cite.
- `expected_remediation` — `direction`, `actions`, `approval_required`,
  `production_impacting`.
- `alternative_hypotheses` — for ambiguous/multi-cause packs: each plausible cause
  with `why_plausible` and `how_to_disambiguate`.
- `missing_information` — what a responder would still need.
- `runbook_references` — runbooks under `knowledge/runbooks/`.
