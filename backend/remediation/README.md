# Remediation recommendations + safety guardrails (KAN-6)

Turns a KAN-5 diagnosis into an **advisory** remediation plan. The agent suggests
operational actions with the context a human needs to act safely — it never
executes anything in the MVP.

## Allowed action categories

`investigate`, `rollback`, `scale`, `restart`, `tune_config`, `page_owner`,
`open_ticket` (see `models.py::ActionCategory`). These are the only actions the
agent may suggest.

## Guardrails (`policy.py`)

Risk and approval are assigned centrally per category — not by individual
recommendations — so they can't be bypassed:

| Category | Risk | Approval | Production-impacting |
| --- | --- | --- | --- |
| investigate | low | no | no |
| page_owner | low | no | no |
| open_ticket | low | no | no |
| scale | medium | **required** | yes |
| tune_config | medium | **required** | yes |
| restart | high | **required** | yes |
| rollback | high | **required** | yes |

- `AUTO_EXECUTION_ENABLED = False` — a global kill-switch.
- `execute()` is intentionally non-functional: any attempt to run a remediation
  raises `AutoExecutionForbidden`, so nothing can silently act on production.

## Recommendation shape

Each `Recommendation` carries: `action`, `title`, `rationale`, `evidence` (from the
diagnosis), `risk`, `rollback_note`, `approval_required`, `production_impacting`,
and `execution = "manual_only"`. A `RemediationPlan` is machine-readable
(`to_dict`/`to_json`, with `auto_execution: false`) and UI-displayable
(`to_markdown`, approval-required actions flagged ⚠️).

## Usage

```bash
python -m backend.remediation db_saturation         # diagnose -> recommend (markdown)
python -m backend.remediation error_rate_spike --json
```

```python
from backend.analysis import diagnose_incident
from backend.remediation import recommend_for
plan = recommend_for(diagnose_incident(incident_dict))
print(plan.to_json())
```

## Acceptance criteria

- Recommendations include action, rationale, evidence, risk, and rollback note.
- Unsafe (destructive/production-impacting) actions are flagged approval-required.
- The system never executes remediation automatically — `execute()` refuses.
- Guardrail behaviour is covered by `tests/test_remediation.py`.
