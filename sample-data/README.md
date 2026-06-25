# Sample data

Synthetic incident datasets used for local development, demos, and evaluation.
No real data or secrets — everything here is fabricated.

## Layout

```
sample-data/
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
- `expected_root_cause` — ground-truth cause + key signals (used for evaluation, KAN-9)

These map to the scenarios defined in `docs/scope.md` and feed the telemetry
ingestion layer (KAN-3), runbook RAG (KAN-4), reasoning workflow (KAN-5), and the
evaluation dataset (KAN-9).
