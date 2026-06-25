"""Optional LLM hook (KAN-5).

The reasoning pipeline is deterministic by default. An ``LLMClient`` can be
supplied to propose richer hypotheses; its output is validated and, if missing
or malformed, the pipeline falls back to the deterministic engine. This keeps the
agent fully functional with no model/API key while leaving a clean extension
point.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Proposes hypotheses from incident context.

    Implementations should return a list of dicts, each with at least
    ``cause`` (str), ``confidence`` (0..1), and ``evidence`` (list[str]); optional
    ``recommended_checks`` and ``missing_information`` lists. Return None/[] (or
    raise) to signal no usable result — the pipeline will fall back.
    """

    @abstractmethod
    def propose(self, context: dict) -> list[dict] | None:
        ...


def validate_llm_hypotheses(raw: object) -> list[dict] | None:
    """Return a cleaned list of hypothesis dicts, or None if unusable.

    A response is considered incomplete (and rejected) if it is not a non-empty
    list of objects that each carry a non-empty cause and at least one piece of
    evidence.
    """
    if not isinstance(raw, list) or not raw:
        return None
    cleaned: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            return None
        cause = item.get("cause")
        evidence = item.get("evidence")
        if not isinstance(cause, str) or not cause.strip():
            return None
        if not isinstance(evidence, list) or not evidence:
            return None
        try:
            confidence = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            return None
        cleaned.append(
            {
                "cause": cause.strip(),
                "confidence": max(0.0, min(1.0, confidence)),
                "evidence": [str(e) for e in evidence],
                "recommended_checks": [str(c) for c in item.get("recommended_checks", [])],
                "missing_information": [str(m) for m in item.get("missing_information", [])],
            }
        )
    return cleaned or None
