"""Evaluation runner (KAN-19)."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.evaluation.checks import CheckResult, score_scenario
from backend.scenarios import loader

EVAL_VERSION = "KAN-19-eval-1"
_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class ScenarioResult:
    slug: str
    scenario_id: str
    agent_scenario: str
    passed: bool
    quality_score: float
    duration_ms: int
    engine: str
    llm_calls: int
    retrieval_calls: int
    predicted_top_cause: str = ""
    top_confidence: float = 0.0
    checks: list[CheckResult] = field(default_factory=list)
    error: str | None = None

    def check(self, name: str) -> CheckResult | None:
        return next((c for c in self.checks if c.name == name), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "scenario_id": self.scenario_id,
            "agent_scenario": self.agent_scenario,
            "passed": self.passed,
            "quality_score": round(self.quality_score, 3),
            "duration_ms": self.duration_ms,
            "engine": self.engine,
            "llm_calls": self.llm_calls,
            "retrieval_calls": self.retrieval_calls,
            "predicted_top_cause": self.predicted_top_cause,
            "top_confidence": round(self.top_confidence, 3),
            "error": self.error,
            "checks": [c.to_dict() for c in self.checks],
        }


@dataclass
class EvaluationReport:
    metadata: dict[str, Any]
    results: list[ScenarioResult]
    generated_at: str

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def pass_rate(self) -> float:
        return self.passed_count / self.total if self.total else 0.0

    @property
    def average_score(self) -> float:
        return sum(r.quality_score for r in self.results) / self.total if self.total else 0.0

    @property
    def avg_top_confidence(self) -> float:
        return sum(r.top_confidence for r in self.results) / self.total if self.total else 0.0

    @property
    def total_duration_ms(self) -> int:
        return sum(r.duration_ms for r in self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "metadata": self.metadata,
            "aggregate": {
                "total": self.total,
                "passed": self.passed_count,
                "failed": self.total - self.passed_count,
                "pass_rate": round(self.pass_rate, 3),
                "average_score": round(self.average_score, 3),
                "avg_top_confidence": round(self.avg_top_confidence, 3),
                "total_duration_ms": self.total_duration_ms,
            },
            "results": [r.to_dict() for r in self.results],
        }


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def gather_metadata(scenario_count: int) -> dict[str, Any]:
    return {
        "eval_version": EVAL_VERSION,
        "commit_sha": _git_sha(),
        "engine": "deterministic",
        "llm_provider": os.environ.get("LLM_PROVIDER", "openai"),
        "llm_model": os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        "llm_invoked": False,
        "prompt_version": "n/a (deterministic analysis engine)",
        "retrieval_backend": "in-process RAG (hashing embedder over knowledge/runbooks)",
        "scenario_count": scenario_count,
    }


def run_scenario(slug: str) -> ScenarioResult:
    from backend.analysis import diagnose_incident
    from backend.remediation import recommend_for

    pack = loader.load_pack(slug)
    incident = loader.to_normalized_incident(pack)
    expected = pack["expected"] or {}

    diagnosis = None
    remediation = None
    engine = "n/a"
    error = None

    start = time.perf_counter()
    try:
        diag_obj = diagnose_incident(incident)
        plan_obj = recommend_for(diag_obj)
        diagnosis = diag_obj.to_dict()
        remediation = plan_obj.to_dict()
        engine = diag_obj.engine or "deterministic"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    duration_ms = int((time.perf_counter() - start) * 1000)

    score = score_scenario(diagnosis, remediation, expected, error)
    hyps = (diagnosis or {}).get("hypotheses") or []
    top = hyps[0] if hyps else {}

    return ScenarioResult(
        slug=slug,
        scenario_id=str(expected.get("id", slug)),
        agent_scenario=str(incident.get("scenario", "unknown")),
        passed=score.passed,
        quality_score=score.quality_score,
        duration_ms=duration_ms,
        engine=engine,
        llm_calls=1 if engine == "llm" else 0,
        retrieval_calls=1 if diagnosis is not None else 0,
        predicted_top_cause=str(top.get("cause", "")),
        top_confidence=float(top.get("confidence", 0.0) or 0.0),
        checks=score.checks,
        error=error,
    )


def resolve_scenarios(selector):
    if not selector or selector == "all":
        return loader.list_packs()
    requested = [s.strip() for s in selector.split(",") if s.strip()]
    known = set(loader.list_packs())
    unknown = [s for s in requested if s not in known]
    if unknown:
        raise ValueError(
            f"unknown scenario(s): {', '.join(unknown)}. "
            f"Available: {', '.join(sorted(known))}"
        )
    return requested


def run_evaluation(slugs=None) -> EvaluationReport:
    slugs = slugs if slugs is not None else loader.list_packs()
    results = [run_scenario(s) for s in slugs]
    metadata = gather_metadata(len(results))
    if results:
        engines = sorted({r.engine for r in results})
        metadata["engine"] = engines[0] if len(engines) == 1 else ",".join(engines)
        metadata["llm_invoked"] = any(r.llm_calls for r in results)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return EvaluationReport(metadata=metadata, results=results, generated_at=generated_at)
