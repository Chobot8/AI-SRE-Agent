"""Unit tests for the investigation persistence mapping (KAN-17).

These exercise the pure ``build_investigation_payload`` transform — no database
or web framework required — so the live-output -> storage mapping is verified in
isolation.
"""

from __future__ import annotations

from backend.api.persistence import build_investigation_payload

_INCIDENT = {
    "id": "INC-1001",
    "scenario": "high_latency",
    "service": "checkout-api",
    "environment": "production",
    "alert": {
        "source": "prometheus",
        "severity": "critical",
        "summary": "checkout-api p99 latency above SLO",
        "labels": {"service": "checkout-api", "region": "eu-central-1"},
    },
    "metrics": [
        {"name": "p99_latency_ms", "unit": "ms", "points": [{"t": "x", "value": 1200}]}
    ],
    "logs": [
        {"level": "ERROR", "service": "checkout-api", "message": "timeout calling orders-db"},
        {"level": "INFO", "service": "checkout-api", "message": "ok"},
    ],
    "expected_root_cause": {"summary": "missing index", "category": "slow_dependency"},
}

_DIAGNOSIS_OK = {
    "incident_id": "INC-1001",
    "service": "checkout-api",
    "scenario": "high_latency",
    "status": "ok",
    "summary": "Slow downstream dependency is the leading cause.",
    "symptoms": ["p99 over SLO", "DB query time rising"],
    "hypotheses": [
        {
            "cause": "Slow downstream dependency / unindexed query",
            "confidence": 0.9,
            "confidence_label": "high",
            "evidence": ["orders-db query time rising"],
            "recommended_checks": ["EXPLAIN the suspect query"],
            "missing_information": ["query plan"],
        },
        {
            "cause": "Resource saturation",
            "confidence": 0.4,
            "confidence_label": "low",
            "evidence": [],
            "recommended_checks": [],
            "missing_information": [],
        },
    ],
    "references": ["[high_latency.md > Remediation]"],
    "engine": "deterministic",
    "error": None,
}

_REMEDIATION = {
    "recommendations": [
        {
            "action": "tune_config",
            "title": "Add the missing index",
            "rationale": "Missing index drives the p99 breach.",
            "evidence": ["missing index on orders.user_id"],
            "risk": "medium",
            "rollback_note": "Drop the index.",
            "approval_required": True,
            "production_impacting": False,
            "execution": "manual_only",
        }
    ]
}


def test_incident_mapping_uses_alert_and_diagnosis() -> None:
    payload = build_investigation_payload(
        incident_request=_INCIDENT,
        diagnosis=_DIAGNOSIS_OK,
        remediation=_REMEDIATION,
        intake_source="manual",
    )
    inc = payload["incident"]
    assert inc["external_ref"] == "INC-1001"
    assert inc["scenario"] == "high_latency"
    assert inc["service"] == "checkout-api"
    assert inc["severity"] == "critical"
    assert inc["environment"] == "production"
    assert inc["status"] == "diagnosed"
    assert inc["alert_source"] == "prometheus"
    assert inc["alert_labels"]["region"] == "eu-central-1"
    assert inc["symptoms"] == ["p99 over SLO", "DB query time rising"]
    assert inc["expected_root_cause"]["category"] == "slow_dependency"


def test_agent_run_and_diagnosis_mapping() -> None:
    payload = build_investigation_payload(
        incident_request=_INCIDENT,
        diagnosis=_DIAGNOSIS_OK,
        remediation=_REMEDIATION,
        run={"status": "succeeded", "latency_ms": 42, "correlation_id": "corr-1"},
    )
    run = payload["agent_run"]
    assert run["status"] == "succeeded"
    assert run["engine"] == "deterministic"
    assert run["latency_ms"] == 42
    assert run["correlation_id"] == "corr-1"

    diag = payload["diagnosis"]
    assert diag["status"] == "ok"
    assert diag["reference_citations"] == ["[high_latency.md > Remediation]"]
    assert diag["is_current"] is True


def test_hypotheses_are_ranked_and_first_is_selected() -> None:
    payload = build_investigation_payload(
        incident_request=_INCIDENT, diagnosis=_DIAGNOSIS_OK, remediation=_REMEDIATION
    )
    hyps = payload["hypotheses"]
    assert [h["rank"] for h in hyps] == [1, 2]
    assert hyps[0]["is_selected"] is True
    assert hyps[1]["is_selected"] is False
    assert hyps[0]["confidence_label"] == "high"


def test_recommendations_mapping() -> None:
    payload = build_investigation_payload(
        incident_request=_INCIDENT, diagnosis=_DIAGNOSIS_OK, remediation=_REMEDIATION
    )
    rec = payload["recommendations"][0]
    assert rec["rank"] == 1
    assert rec["action_category"] == "tune_config"
    assert rec["risk_level"] == "medium"
    assert rec["approval_required"] is True
    assert rec["execution_status"] == "manual_only"


def test_evidence_built_from_metrics_and_notable_logs() -> None:
    payload = build_investigation_payload(
        incident_request=_INCIDENT, diagnosis=_DIAGNOSIS_OK, remediation=_REMEDIATION
    )
    kinds = [e["kind"] for e in payload["evidence"]]
    assert "metric" in kinds  # from the p99 metric
    assert "log" in kinds  # from the ERROR log
    # The INFO log is not notable and must be excluded.
    assert all("ok" not in (e.get("summary") or "") for e in payload["evidence"])
    metric_ev = next(e for e in payload["evidence"] if e["kind"] == "metric")
    assert metric_ev["detail"]["last_value"] == 1200


def test_retrieved_chunks_pass_through() -> None:
    chunks = [{"source": "high_latency.md", "score": 0.87, "citation": "[x]"}]
    payload = build_investigation_payload(
        incident_request=_INCIDENT,
        diagnosis=_DIAGNOSIS_OK,
        remediation=_REMEDIATION,
        retrieved_chunks=chunks,
    )
    assert payload["retrieved_chunks"] == chunks


def test_failed_diagnosis_maps_to_failed_run_and_no_hypotheses() -> None:
    failed = {
        "incident_id": "INC-1001",
        "service": "checkout-api",
        "scenario": "high_latency",
        "status": "error",
        "summary": "",
        "symptoms": [],
        "hypotheses": [],
        "references": [],
        "engine": "deterministic",
        "error": "forced failure",
    }
    payload = build_investigation_payload(
        incident_request=_INCIDENT,
        diagnosis=failed,
        remediation={"recommendations": []},
        run={"status": "failed", "error_message": "forced failure"},
    )
    assert payload["incident"]["status"] == "investigating"
    assert payload["agent_run"]["status"] == "failed"
    assert payload["agent_run"]["error_message"] == "forced failure"
    assert payload["diagnosis"]["status"] == "error"
    assert payload["diagnosis"]["error"] == "forced failure"
    assert payload["hypotheses"] == []
