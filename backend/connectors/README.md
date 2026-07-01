# SRE tool connectors (KAN-22)

Connectors to the systems a live SRE agent would call while investigating an
incident: metrics, logs, cluster health, ticketing, and runbooks. Separate
from `backend/telemetry/connectors` (KAN-3), which normalizes a fixed incident
payload once at replay time -- these model the *ad hoc*, on-demand calls a
future agent tool-calling loop would make (pull more metrics, check pod
health, open a follow-up ticket, look up a runbook), so they carry a timeout
and structured error model that batch ingestion did not need.

## Status: real, mocked, or planned

| Interface | Mock (default, used everywhere) | Real implementation | Status |
| --- | --- | --- | --- |
| `MetricsConnector` | `MockPrometheusConnector` -- serves `scenarios/*/metrics.json` | `PrometheusConnector` -- calls `/api/v1/query_range` over stdlib `urllib` | **Real, inert by default.** Set `PROMETHEUS_BASE_URL` to activate. |
| `LogsConnector` | `MockLokiConnector` -- serves `scenarios/*/logs.jsonl` | `LokiConnector` -- calls `/loki/api/v1/query_range` | **Real, inert by default.** Set `LOKI_BASE_URL` to activate. |
| `KubernetesConnector` | `MockKubernetesConnector` -- serves `scenarios/*/service_health.json` | `KubernetesApiConnector` -- calls the K8s REST API (`GET .../pods`) | **Real, inert by default.** Set `KUBERNETES_API_BASE_URL` (+ `KUBERNETES_BEARER_TOKEN`) to activate. |
| `TicketingConnector` | `MockTicketingConnector` -- in-memory ticket store | `JiraTicketingConnector` -- Jira Cloud REST API v3 (create issue / add comment) | **Real, inert by default.** Set `JIRA_BASE_URL` + `JIRA_EMAIL` + `JIRA_API_TOKEN` to activate. |
| `RunbookConnector` | `MockRunbookConnector` -- keyword search over `knowledge/runbooks/*.md` + `scenarios/*/runbook.md` | `RunbookDocsConnector` -- `GET {base_url}/search?q=...` against a configurable doc source | **Real, inert by default.** Set `RUNBOOK_SOURCE_BASE_URL` to activate. |

Every "real" implementation is genuinely wired (issues an actual HTTP call
with stdlib `urllib`, no extra dependency) but **inert until configured**: with
no `base_url` set it returns a `not_configured` `ConnectorError` and makes no
network call. Nothing here is a bare `NotImplementedError` stub -- see
`backend/connectors/*.py` for the request-building/response-mapping code each
one runs once pointed at a real system. This satisfies the ticket's "no
connector requires real production credentials for the local demo" criterion:
the mocks (used by every scenario pack, the CLI demo, and the test suite) need
nothing, and the real connectors stay dormant until you opt in.

**Not planned / out of scope for this ticket:** an `AlertConnector`
equivalent already exists in `backend/telemetry/connectors` (KAN-3) for
ingestion; this package does not duplicate it. A live agent tool-calling loop
that actually *invokes* these connectors mid-investigation is future work --
KAN-22 only defines and mocks the contracts so that loop has something clean
to call.

## Interface contract (`base.py`)

Every connector method takes a typed request and returns a typed result
(`schemas.py`) that extends `ConnectorResult`:

```python
@dataclass
class ConnectorResult:
    source: str = "mock"            # "mock" | "real"
    error: ConnectorError | None = None
    latency_ms: float | None = None

    @property
    def ok(self) -> bool: ...
    def diagnostic_notes(self) -> list[str]: ...
```

A failed call **never raises** -- it returns `ok=False` with a structured
`ConnectorError` (`kind` is one of `timeout`, `not_configured`, `not_found`,
`auth`, `unavailable`, `invalid_response`, `rate_limited`). Callers append
`result.diagnostic_notes()` to a diagnosis's evidence/warnings list instead of
handling an exception:

```python
metrics = connector.query_range(request)
if not metrics.ok:
    diagnosis.symptoms += metrics.diagnostic_notes()   # e.g. "[prometheus] not_found: ..."
else:
    ...
```

Timeouts are enforced by `call_with_timeout()`, which runs the call in a
worker thread under a hard wall-clock budget (`ConnectorConfig.timeout_seconds`,
default 5s) and converts *any* exception -- not just a timeout -- into a
`ConnectorError` so a connector method never lets a raw exception escape.

## Credentials/configuration reference

All settings are optional (`backend/config.py`, env-driven via `.env`; see
`.env.example`). Unset means the real connector is inert.

| Connector | Env vars | Notes |
| --- | --- | --- |
| Prometheus | `PROMETHEUS_BASE_URL`, `PROMETHEUS_TIMEOUT_SECONDS` | No auth modeled by default (most in-cluster Prometheus is reached over a trusted network); add a bearer token via `ConnectorConfig.api_token` if your deployment needs one. |
| Loki | `LOKI_BASE_URL`, `LOKI_TIMEOUT_SECONDS` | Same auth note as Prometheus. |
| Kubernetes | `KUBERNETES_API_BASE_URL`, `KUBERNETES_BEARER_TOKEN`, `KUBERNETES_VERIFY_TLS`, `KUBERNETES_TIMEOUT_SECONDS` | Token should be a **read-only, pods/deployments-scoped** service-account token -- never a cluster-admin key. |
| Jira | `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_TIMEOUT_SECONDS` | `JIRA_API_TOKEN` is an Atlassian API token (Basic auth with the email), never the account password. Distinct from the Jira/Atlassian *MCP* used for this repo's own KAN-** ticket workflow -- this connector is the agent's own follow-up-ticket tool. |
| Runbook docs | `RUNBOOK_SOURCE_BASE_URL`, `RUNBOOK_SOURCE_API_TOKEN`, `RUNBOOK_TIMEOUT_SECONDS` | Assumes a simple `GET /search?q=...` JSON API; adjust `_map_response` in `runbook.py` for a real system (Confluence, Notion, an internal docs service). |

`backend/connectors/settings.py` centralizes the mapping from `Settings` to
each connector's `ConnectorConfig`.

## Mock connectors and the scenario packs

Mock connectors read the same git-committed fixtures already used elsewhere,
so they power every pack under `scenarios/` (KAN-18) with no separate fixture
data to maintain:

* `MockPrometheusConnector` / `MockLokiConnector` -- `metrics.json` / `logs.jsonl`
* `MockKubernetesConnector` -- `service_health.json` (desired/ready replicas +
  dependency status; individual pod objects are synthesized from the replica
  counts since the fixture only records aggregates -- see
  `_synthesize_pods` in `kubernetes.py`)
* `MockRunbookConnector` -- each pack's `runbook.md` plus `knowledge/runbooks/*.md`
* `MockTicketingConnector` -- no fixture needed; an in-memory ticket store

They also fall back to the five flatter `sample-data/incidents/*.json`
samples, so `high_latency`, `db_saturation`, etc. resolve too.

```bash
python -m backend.connectors list                    # scenario slugs
python -m backend.connectors demo checkout-crashloop-badenv   # exercise all 5 connectors
pytest tests/test_connectors.py
```

## Advisory-only ticketing

Like `backend/remediation`, `TicketingConnector.create_ticket`/`add_comment`
are never called as a side effect of a diagnosis alone -- something explicit
(a human, or an approved `open_ticket` remediation step) triggers them. This
resolves the ticket's open question ("read-only/comment-only first, or create
tickets?") as: implement both behind the same advisory-only contract, since
the guardrail is *who/what triggers the call*, not which Jira operation it is.

## Adding/completing a real connector

1. Subclass the relevant interface in `base.py`.
2. Read connection details from a `ConnectorConfig` (build it via
   `backend/connectors/settings.py` from `backend.config.get_settings()`).
3. Wrap the network call in `call_with_timeout()`.
4. Return a `not_configured` `ConnectorError` when `config.base_url` is unset.

Nothing downstream changes -- callers only depend on the interface and the
typed result, exactly as the KAN-3 telemetry connectors already do for
ingestion.
