"""Kubernetes connector (KAN-22).

``MockKubernetesConnector`` serves service/pod health from the scenario packs'
``service_health.json`` snapshots -- no cluster access, no credentials.
``KubernetesApiConnector`` is the real placeholder: once ``kubernetes_api_base_url``
and a bearer token are configured, it queries the Kubernetes REST API directly
over stdlib ``urllib`` (no client library dependency); until then every call
returns a ``not_configured`` error rather than failing.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from backend.connectors.base import (
    ConnectorConfig,
    ConnectorError,
    ConnectorErrorKind,
    KubernetesConnector,
    call_with_timeout,
    ssl_context_for,
)
from backend.connectors.scenario_source import ScenarioFixture, find_scenario_slug_for_service
from backend.connectors.schemas import (
    DependencyStatus,
    PodStatus,
    ServiceHealthQuery,
    ServiceHealthResult,
)


def _synthesize_pods(service: str, status: str, desired: int, ready: int) -> list[PodStatus]:
    """Build per-pod entries from the pack's aggregate replica counts.

    ``scenarios/<slug>/service_health.json`` only records desired/ready replica
    counts, not individual pods -- a real Kubernetes connector would return
    actual pod objects from the API. This synthesizes plausible-looking pod
    entries so ``ServiceHealthResult.pods`` is populated the same shape either
    way, which keeps downstream code connector-agnostic.
    """
    not_ready_phase = "CrashLoopBackOff" if status == "down" else "Pending"
    pods = [
        PodStatus(name=f"{service}-{i}", phase="Running", ready=True, restart_count=0)
        for i in range(ready)
    ]
    pods += [
        PodStatus(
            name=f"{service}-{i}",
            phase=not_ready_phase,
            ready=False,
            restart_count=1 if not_ready_phase == "CrashLoopBackOff" else 0,
            last_termination_reason="Error" if not_ready_phase == "CrashLoopBackOff" else None,
        )
        for i in range(ready, desired)
    ]
    return pods


class MockKubernetesConnector(KubernetesConnector):
    """Placeholder Kubernetes connector backed by local mock fixtures."""

    name = "kubernetes"

    def get_service_health(self, request: ServiceHealthQuery) -> ServiceHealthResult:
        started = time.monotonic()
        slug = request.incident_ref or find_scenario_slug_for_service(request.service)

        health: dict | None = None
        if slug:
            fixture = ScenarioFixture(slug)
            if fixture.exists():
                health = fixture.service_health()

        latency_ms = (time.monotonic() - started) * 1000
        if health is None:
            return ServiceHealthResult(
                service=request.service,
                latency_ms=latency_ms,
                error=ConnectorError(
                    connector=self.name,
                    kind=ConnectorErrorKind.NOT_FOUND,
                    message=(
                        f"no mock service-health snapshot for service={request.service!r} "
                        f"incident_ref={request.incident_ref!r}"
                    ),
                ),
            )

        replicas = health.get("replicas", {})
        desired = int(replicas.get("desired", 0))
        ready = int(replicas.get("ready", 0))
        status = health.get("status", "unknown")
        dependencies = [
            DependencyStatus(
                name=d.get("name", ""),
                type=d.get("type", ""),
                status=d.get("status", "unknown"),
                latency_ms=d.get("latency_ms"),
                error_rate=d.get("error_rate"),
            )
            for d in health.get("dependencies", [])
        ]
        return ServiceHealthResult(
            latency_ms=latency_ms,
            service=request.service,
            status=status,
            version=health.get("version"),
            replicas_desired=desired,
            replicas_ready=ready,
            pods=_synthesize_pods(request.service, status, desired, ready),
            dependencies=dependencies,
        )


class KubernetesApiConnector(KubernetesConnector):
    """Real Kubernetes connector -- inert until the API base URL/token are set.

    Configuration (``backend.config.Settings`` / ``.env.example``):
        KUBERNETES_API_BASE_URL     e.g. ``https://<cluster>:6443``
        KUBERNETES_BEARER_TOKEN     a service-account token scoped read-only to
                                     pods/deployments (never a cluster-admin key)
        KUBERNETES_VERIFY_TLS       set false only for local/self-signed test clusters
        KUBERNETES_TIMEOUT_SECONDS

    Uses the plain Kubernetes REST API (``GET /api/v1/namespaces/{ns}/pods``)
    rather than the ``kubernetes`` client library, so no extra dependency is
    required for this placeholder to be genuinely callable.
    """

    name = "kubernetes"

    def __init__(self, config: ConnectorConfig | None = None) -> None:
        self.config = config or ConnectorConfig()

    def get_service_health(self, request: ServiceHealthQuery) -> ServiceHealthResult:
        if not self.config.configured:
            return ServiceHealthResult(
                source="real",
                service=request.service,
                error=ConnectorError(
                    connector=self.name,
                    kind=ConnectorErrorKind.NOT_CONFIGURED,
                    message=(
                        "KUBERNETES_API_BASE_URL is not set; see backend/connectors/README.md"
                    ),
                ),
            )

        def _do_call() -> ServiceHealthResult:
            selector = urllib.parse.quote(f"app={request.service}")
            url = (
                f"{self.config.base_url}/api/v1/namespaces/{request.namespace}"
                f"/pods?labelSelector={selector}"
            )
            headers = {"Accept": "application/json"}
            if self.config.api_token:
                headers["Authorization"] = f"Bearer {self.config.api_token}"
            req = urllib.request.Request(url, headers=headers)
            context = ssl_context_for(self.config)
            with urllib.request.urlopen(
                req, timeout=self.config.timeout_seconds, context=context
            ) as resp:
                payload = json.loads(resp.read())
            return _map_pod_list(payload, request.service)

        result, error = call_with_timeout(
            _do_call, timeout_seconds=self.config.timeout_seconds, connector=self.name
        )
        if error is not None:
            return ServiceHealthResult(source="real", service=request.service, error=error)
        assert result is not None
        result.source = "real"
        return result


def _map_pod_list(payload: dict, service: str) -> ServiceHealthResult:
    items = payload.get("items")
    if items is None:
        return ServiceHealthResult(
            service=service,
            error=ConnectorError(
                connector="kubernetes",
                kind=ConnectorErrorKind.INVALID_RESPONSE,
                message="response has no 'items' field (expected a PodList)",
            ),
        )
    pods: list[PodStatus] = []
    ready_count = 0
    for item in items:
        status = item.get("status", {})
        phase = status.get("phase", "Unknown")
        container_statuses = status.get("containerStatuses", [])
        ready = bool(container_statuses) and all(c.get("ready") for c in container_statuses)
        restart_count = sum(c.get("restartCount", 0) for c in container_statuses)
        last_reason = None
        for c in container_statuses:
            terminated = c.get("lastState", {}).get("terminated")
            if terminated:
                last_reason = terminated.get("reason")
        if ready:
            ready_count += 1
        pods.append(
            PodStatus(
                name=item.get("metadata", {}).get("name", "unknown"),
                phase=phase,
                ready=ready,
                restart_count=restart_count,
                last_termination_reason=last_reason,
            )
        )
    return ServiceHealthResult(
        service=service,
        status="healthy" if ready_count == len(pods) and pods else "degraded",
        replicas_desired=len(pods),
        replicas_ready=ready_count,
        pods=pods,
    )
