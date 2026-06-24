# Telemetry connectors

Connectors pull incident context from observability sources and return it in the
**normalized schema** (`backend/telemetry/schema.py`). The MVP ships placeholder
implementations backed by mock data in `sample-data/`; real connectors implement
the same interfaces, so the ingestion pipeline is unchanged when a source is
swapped.

## Interfaces (`base.py`)

| Interface | Method | Returns | Placeholder | Real source |
| --------- | ------ | ------- | ----------- | ----------- |
| `MetricsConnector` | `fetch_metrics(ref)` | `list[Metric]` | `PrometheusMetricsConnector` | Prometheus `/api/v1/query_range` |
| `LogsConnector` | `fetch_logs(ref)` | `list[LogEntry]` | `LokiLogsConnector` | Loki `/loki/api/v1/query_range` |
| `AlertConnector` | `fetch_alert(ref)` / `normalize(payload)` | `Alert` | `MockAlertConnector` | Alertmanager / PagerDuty webhook |
| `DashboardConnector` | `fetch_dashboard_links(ref)` | `list[str]` | `GrafanaDashboardConnector` | Grafana `/api/search` |

`ref` (the incident reference) is a scenario name in the mock implementation; in a
real connector it would be an incident ID, service + time window, or alert label set.

## Adding a real connector

```python
from backend.telemetry.connectors.base import MetricsConnector
from backend.telemetry.schema import Metric

class RealPrometheusConnector(MetricsConnector):
    def __init__(self, base_url: str):
        self.base_url = base_url

    def fetch_metrics(self, incident_ref: str) -> list[Metric]:
        # 1. issue PromQL range queries against self.base_url
        # 2. map each result series onto Metric(name=..., unit=..., points=[...])
        ...
```

Then register it when building the ingestor (see `ingest.py::build_default_ingestor`)
instead of the placeholder. Nothing downstream changes — the pipeline only depends
on the interface and the normalized types.

## Run the mock ingestion

```bash
python -m backend.telemetry                 # ingest all scenarios
python -m backend.telemetry high_latency    # ingest one scenario
```

Normalized incidents are written under `data/normalized/`, raw payloads under
`data/raw/` (both git-ignored).
