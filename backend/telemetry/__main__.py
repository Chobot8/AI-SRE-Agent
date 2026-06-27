"""Demo runner for the telemetry ingestion layer (KAN-3).

Usage:
    python -m backend.telemetry            # ingest all sample scenarios
    python -m backend.telemetry high_latency   # ingest one scenario

Prints a short summary per incident and writes normalized data under data/.
"""

from __future__ import annotations

import sys

from backend.telemetry.ingest import build_default_ingestor


def main(argv: list[str]) -> int:
    ingestor = build_default_ingestor()
    scenarios = argv or ingestor.source.available_scenarios()
    if not scenarios:
        print("No sample scenarios found under sample-data/incidents/.")
        return 1

    for scenario in scenarios:
        incident = ingestor.ingest(scenario)
        print(
            f"[{incident.id}] {incident.scenario.value} | {incident.service} "
            f"({incident.environment.value}) -> "
            f"alert='{incident.alert.summary}', "
            f"{len(incident.metrics)} metric series, {len(incident.logs)} log lines"
        )
    print("\nNormalized incidents written under data/normalized/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
