# Sample data

Synthetic incident datasets used for local development, demos, and evaluation.
No real data or secrets — everything here is fabricated.

## Layout

```
sample-data/
├── evaluation/
│   └── baseline.json           # KAN-9 baseline expectations for local eval tests
├── schema/
│   └── incident.schema.json   # JSON Schema for a normalized incident
└── incidents/
    ├── high_latency.json
    ├── error_rate_spike.json
    ├── pod_crash_loop.json
    ├── queue_backlog.json
    └── db_saturation.json
```

## Normalized incident shape

Each incident file follows `schema/incident.schema.json`:

- `id`, `scenario`, `service`, `environment`
- `alert` — the inbound alert payload (source, severity, summary, started_at, labels)
- `metrics` — list of `{ name, unit, description, points: [{ t, value }] }`
- `logs` — list of `{ t, level, service, message }`
- `expected_root_cause` — ground-truth cause, key signals, and runbook references
  (used for evaluation, KAN-9)

These map to the scenarios defined in `docs/scope.md` and feed the telemetry
ingestion layer (KAN-3), runbook RAG (KAN-4), reasoning workflow (KAN-5), and the
evaluation dataset (KAN-9).

## Evaluation baseline

`evaluation/baseline.json` records the deterministic baseline before prompt or
retrieval tuning. It maps each scenario to the expected root-cause category, the
substring expected in the top diagnosis hypothesis, and the matching runbook.

Run the evaluation checks locally with:

```bash
pytest tests/test_evaluation.py
```

The tests validate:

- all five bundled scenarios are represented in the baseline
- each incident has expected root cause, key signals, metrics, logs, and runbook references
- RAG retrieval returns the matching runbook first for every scenario
- diagnosis output has a summary, symptoms, references, evidence, and recommended checks
