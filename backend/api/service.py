"""Diagnosis service layer (KAN-7).

Framework-agnostic orchestration behind the API: submit/replay an incident, run
the analysis (KAN-5) + remediation (KAN-6), store the result, and fetch it by id.
Kept free of FastAPI so it can be unit-tested without the web stack.

Instrumented for observability (KAN-12): every diagnosis runs inside a
correlation context, logs its major workflow steps, and records a metric.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from backend.analysis import diagnose_incident
from backend.api.persistence import (
    build_investigation_payload,
    persist_investigation,
    persistence_enabled,
)
from backend.observability import (
    METRICS,
    correlation_context,
    get_correlation_id,
    get_logger,
    log_event,
)
from backend.remediation import recommend_for

_log = get_logger("service")


def _sample_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "sample-data" / "incidents"


class DiagnosisService:
    """Runs diagnoses and keeps results in an in-memory store."""

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}
        self._retriever = None  # built lazily for retrieved-chunk persistence

    def submit(self, incident: dict, *, is_replay: bool = False) -> dict:
        """Diagnose + recommend for an incident; store and return a receipt.

        Runs under a correlation ID (reusing the request's if one is bound) that
        is attached to the stored result and every log line for the diagnosis.
        When a database is configured the full investigation is also persisted to
        PostgreSQL (best-effort: a storage failure never breaks the live result).
        """
        with correlation_context(get_correlation_id()) as correlation_id:
            scenario = "unknown"
            incident_id = "unknown"
            if isinstance(incident, dict):
                scenario = str(incident.get("scenario", "unknown"))
                incident_id = str(incident.get("id", "unknown"))
            log_event(_log, "diagnosis.received", scenario=scenario, incident_id=incident_id)

            start = time.perf_counter()
            diagnosis = diagnose_incident(incident)
            plan = recommend_for(diagnosis)
            latency_ms = int((time.perf_counter() - start) * 1000)

            diagnosis_id = uuid.uuid4().hex
            result = {
                "diagnosis_id": diagnosis_id,
                "correlation_id": correlation_id,
                **diagnosis.to_dict(),
                "remediation": plan.to_dict(),
            }
            self._store[diagnosis_id] = result

            engine = diagnosis.engine or "none"
            METRICS.diagnoses_total.inc(status=diagnosis.status, engine=engine)
            log_event(
                _log,
                "diagnosis.completed",
                diagnosis_id=diagnosis_id,
                status=diagnosis.status,
                engine=engine,
                hypotheses=len(diagnosis.hypotheses),
            )

            investigation_id = self._persist(
                incident=incident,
                diagnosis=diagnosis,
                plan=plan,
                correlation_id=correlation_id,
                latency_ms=latency_ms,
                is_replay=is_replay,
            )
            if investigation_id is not None:
                result["investigation_id"] = investigation_id

            return {
                "diagnosis_id": diagnosis_id,
                "correlation_id": correlation_id,
                "incident_id": diagnosis.incident_id,
                "status": diagnosis.status,
                "investigation_id": investigation_id,
            }

    def _persist(
        self,
        *,
        incident: dict,
        diagnosis,
        plan,
        correlation_id: str,
        latency_ms: int,
        is_replay: bool,
    ) -> str | None:
        """Persist the full investigation to PostgreSQL; return its incident id.

        Returns None when persistence is disabled or fails (the live, in-memory
        result is always available regardless).
        """
        if not isinstance(incident, dict) or not persistence_enabled():
            return None
        try:
            run_status = "succeeded" if diagnosis.status == "ok" else "failed"
            run = {
                "status": run_status,
                "latency_ms": latency_ms,
                "correlation_id": correlation_id,
            }
            if diagnosis.status != "ok":
                run["error_type"] = "diagnosis_error"
                run["error_message"] = diagnosis.error
            payload = build_investigation_payload(
                incident_request=incident,
                diagnosis=diagnosis.to_dict(),
                remediation=plan.to_dict(),
                retrieved_chunks=self._retrieve_chunks(incident),
                run=run,
                intake_source="replay" if is_replay else "manual",
                is_replay=is_replay,
            )
            ids = persist_investigation(payload)
            investigation_id = ids.get("incident_id")
            log_event(
                _log,
                "investigation.persisted",
                investigation_id=investigation_id,
                run_status=run_status,
            )
            return investigation_id
        except Exception as exc:  # best-effort: never break the live response
            log_event(_log, "persistence.failed", error=type(exc).__name__)
            return None

    def _retrieve_chunks(self, incident: dict) -> list[dict]:
        """Best-effort RAG retrieval, mapped to retrieved_chunks rows."""
        try:
            from backend.rag import Retriever, build_index, query_from_incident

            if self._retriever is None:
                self._retriever = Retriever(build_index())
            hits = self._retriever.retrieve(query_from_incident(incident), k=3)
            return [
                {
                    "source": h.chunk.source,
                    "heading": h.chunk.heading,
                    "citation": h.citation,
                    "chunk_text": h.chunk.text,
                    "score": float(h.score),
                    "vector_store": "inproc:runbooks",
                }
                for h in hits
            ]
        except Exception:  # retrieval is optional context
            return []

    def get(self, diagnosis_id: str) -> dict | None:
        """Return the full stored diagnosis result, or None."""
        return self._store.get(diagnosis_id)

    def available_scenarios(self) -> list[str]:
        d = _sample_dir()
        return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []

    def load_sample(self, scenario: str) -> dict | None:
        path = _sample_dir() / f"{scenario}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def replay(self, scenario: str) -> dict | None:
        """Submit a bundled sample scenario; None if the scenario is unknown."""
        sample = self.load_sample(scenario)
        if sample is None:
            return None
        return self.submit(sample, is_replay=True)


_service: DiagnosisService | None = None


def get_service() -> DiagnosisService:
    """Return the process-wide service singleton (FastAPI dependency)."""
    global _service
    if _service is None:
        _service = DiagnosisService()
    return _service
