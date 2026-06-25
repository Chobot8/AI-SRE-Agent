"""RAG demo / index CLI (KAN-4).

Usage:
    python -m backend.rag build                 # build + save the index
    python -m backend.rag query "high latency p99 slo orders-db slow query"
    python -m backend.rag incident high_latency # retrieve for a sample incident
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from backend.rag.index import build_index, default_index_path
from backend.rag.retriever import Retriever, format_grounded_answer, query_from_incident


def _sample_incident(scenario: str) -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "sample-data" / "incidents" / f"{scenario}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "build"
    index_path = default_index_path()

    if cmd == "build":
        store = build_index(save_to=index_path)
        print(f"Indexed {len(store)} chunks from {len(store.sources())} runbooks.")
        print(f"Saved index to {index_path}")
        return 0

    store = build_index(save_to=index_path)
    retriever = Retriever(store)

    if cmd == "query":
        query = " ".join(argv[1:]) or "high latency"
    elif cmd == "incident":
        query = query_from_incident(_sample_incident(argv[1] if len(argv) > 1 else "high_latency"))
    else:
        print(__doc__)
        return 1

    hits = retriever.retrieve(query, k=3)
    answer = f"Top operational context for: {query[:80]}..."
    print(format_grounded_answer(answer, hits))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
