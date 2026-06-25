# Incident analysis & root-cause hypotheses (KAN-5)

Turns a normalized incident (KAN-3) into a structured, ranked diagnosis, grounded
in the runbook knowledge base (KAN-4).

## Pipeline

```
incident (normalized)
   │  summarize alert
   │  collect context  ── metrics/log detectors ─┐
   │                    └ runbook retrieval (RAG) ┤
   ▼                                              │
identify symptoms ──► rank likely causes ──► propose next checks
                                  │
                                  ▼
                       IncidentDiagnosis
              (summary, symptoms, ranked hypotheses,
               evidence, checks, missing info, references)
```

## Output shape

`IncidentDiagnosis` (see `models.py`) is machine-readable (`to_dict`/`to_json`)
and UI-displayable (`to_markdown`). Each `Hypothesis` carries:

- `cause`
- `confidence` (0..1) + `confidence_label` (low/medium/high)
- `evidence` — the concrete metrics/logs that support it
- `recommended_checks` — the next diagnostic steps
- `missing_information` — what's still needed to confirm

## How ranking works

`detectors.py` extracts canonical signal tokens (metric trends + log keywords)
with evidence strings. `knowledge.py` holds per-scenario cause templates — the
same operational logic the runbooks describe, encoded for scoring. The pipeline
scores each template by signal coverage × base confidence and ranks the results.
If nothing matches, a low-confidence "manual investigation" hypothesis is returned
(never an empty result).

## Deterministic by default, LLM optional

The engine is fully deterministic and needs no model or API key. Supply an
`LLMClient` (see `llm.py`) to propose richer hypotheses; its output is validated,
and if incomplete or malformed the pipeline **falls back to the deterministic
engine**. The `engine` field records which path produced the result.

## Failure handling

A malformed incident (missing `id`/`scenario`/`alert`, or not an object) returns
an `IncidentDiagnosis` with `status="error"` and a diagnostic `error` message —
never an exception or empty response.

## Usage

```bash
python -m backend.analysis high_latency          # readable diagnosis
python -m backend.analysis db_saturation --json  # machine-readable JSON
```

```python
from backend.analysis import diagnose_incident
diagnosis = diagnose_incident(incident_dict)      # IncidentDiagnosis
print(diagnosis.to_json())
```
