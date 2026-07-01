"""Demo runner for the KAN-22 connectors.

Usage:
    python -m backend.connectors demo <scenario-slug>   # run all 5 mock connectors
    python -m backend.connectors list                   # list available scenario slugs

Exercises every mock connector (Prometheus, Loki, Kubernetes, Jira, runbook)
against one scenario pack and prints each result, so it doubles as a quick
manual check that "mock connectors can power all existing scenario packs".
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from backend.connectors.jira import MockTicketingConnector
from backend.connectors.kubernetes import MockKubernetesConnector
from backend.connectors.loki import MockLokiConnector
from backend.connectors.prometheus import MockPrometheusConnector
from backend.connectors.runbook import MockRunbookConnector
from backend.connectors.scenario_source import ScenarioFixture, available_scenario_slugs
from backend.connectors.schemas import (
    AddCommentRequest,
    CreateTicketRequest,
    LogsQuery,
    MetricsQuery,
    RunbookQuery,
    ServiceHealthQuery,
)


def _demo(slug: str) -> int:
    fixture = ScenarioFixture(slug)
    if not fixture.exists():
        print(f"Unknown scenario pack: {slug!r}. Try: python -m backend.connectors list")
        return 1
    alert = fixture.alert() or {}
    service = alert.get("service", slug)
    now = datetime.now(tz=timezone.utc)
    window_start = now - timedelta(hours=1)

    print(f"=== {slug} (service={service}) ===\n")

    metrics = MockPrometheusConnector().query_range(
        MetricsQuery(service=service, query="", start=window_start, end=now, incident_ref=slug)
    )
    print(f"[prometheus] ok={metrics.ok} series={len(metrics.series)}", metrics.diagnostic_notes())

    logs = MockLokiConnector().query_range(LogsQuery(service=service, incident_ref=slug))
    print(f"[loki]       ok={logs.ok} lines={len(logs.lines)}", logs.diagnostic_notes())

    health = MockKubernetesConnector().get_service_health(
        ServiceHealthQuery(service=service, incident_ref=slug)
    )
    print(
        f"[kubernetes] ok={health.ok} status={health.status} "
        f"replicas={health.replicas_ready}/{health.replicas_desired}",
        health.diagnostic_notes(),
    )

    runbook_query = RunbookQuery(query=slug.replace("-", " "), service=service)
    runbook = MockRunbookConnector().search(runbook_query)
    print(
        f"[runbook]    ok={runbook.ok} docs={[d.id for d in runbook.docs]}",
        runbook.diagnostic_notes(),
    )

    jira = MockTicketingConnector()
    ticket = jira.create_ticket(
        CreateTicketRequest(
            project_key="KAN",
            summary=f"Follow-up: {alert.get('summary', slug)}",
            description=f"Auto-drafted follow-up for scenario {slug}.",
            incident_ref=slug,
        )
    )
    comment_request = AddCommentRequest(
        ticket_id=ticket.ticket_id or "", body="Diagnosis attached."
    )
    comment = jira.add_comment(comment_request)
    print(f"[jira]       created={ticket.ticket_id} commented_ok={comment.ok}")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "list":
        for slug in available_scenario_slugs():
            print(slug)
        return 0
    if argv[0] == "demo" and len(argv) > 1:
        return _demo(argv[1])
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
