"""Index builder (KAN-4, extended KAN-21).

Builds the vector store from the source runbooks. The store is rebuildable at any
time from ``knowledge/runbooks`` -- nothing is hand-edited in the index itself.

KAN-21: every chunk built here now carries metadata (document_type, source,
incident_type inferred from the runbook filename), and ``build_index`` can
optionally also index each scenario pack's ``runbook.md`` snippet (KAN-18),
tagged with that pack's service/incident_type/severity/environment -- so
retrieval can cover scenario-specific runbooks, not just the generic
knowledge base, without hard-coding any one scenario (every pack under
``scenarios/`` is discovered and chunked identically).

``include_scenario_packs`` defaults to ``False`` so ``build_index()``'s output
is byte-for-byte the same set of chunks/vectors as before KAN-21 -- existing
retrieval-quality tests (which assert an exact top-hit source) are unaffected.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.rag.chunking import chunk_file, chunk_markdown
from backend.rag.embeddings import Embedder, HashingEmbedder
from backend.rag.models import Chunk
from backend.rag.vector_store import VectorStore


def default_runbooks_dir() -> Path:
    """Repo-root ``knowledge/runbooks`` directory."""
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "knowledge" / "runbooks"


def default_scenarios_dir() -> Path:
    """Repo-root ``scenarios`` directory (KAN-18 packs)."""
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "scenarios"


def default_index_path() -> Path:
    """Repo-root ``data/rag/index.json`` (generated, git-ignored)."""
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "rag" / "index.json"


def _runbook_documents(runbooks_dir: Path) -> list[Chunk]:
    """Chunk every ``knowledge/runbooks/*.md`` file, tagged with metadata."""
    files = sorted(runbooks_dir.glob("*.md"))
    if not files:
        raise FileNotFoundError(f"No runbooks (*.md) found in {runbooks_dir}")
    chunks: list[Chunk] = []
    for path in files:
        metadata = {
            "document_type": "runbook",
            "source": path.name,
            # The runbook filename is the scenario it covers, e.g.
            # "high_latency.md" -> incident_type "high_latency". Derived from
            # the filename generically -- no scenario name is hard-coded here.
            "incident_type": path.stem,
        }
        chunks.extend(chunk_file(path, metadata=metadata))
    return chunks


def _pack_slugs_under(scenarios_dir: Path) -> list[str]:
    """Slugs of every *complete* pack (has ``expected.yaml``) under
    ``scenarios_dir``, mirroring ``backend.scenarios.loader.list_packs`` but
    parameterized by directory so a custom/test ``scenarios_dir`` is honored."""
    if not scenarios_dir.exists():
        return []
    return sorted(
        p.name
        for p in scenarios_dir.iterdir()
        if p.is_dir() and p.name != "schema" and (p / "expected.yaml").exists()
    )


def _load_pack_under(scenarios_dir: Path, slug: str) -> dict[str, Any]:
    """Load one pack's ``alert``/``expected``/``runbook`` directly from
    ``scenarios_dir/slug`` -- independent of ``backend.scenarios.loader``'s
    module-level (repo-root) ``SCENARIOS_DIR``, so a custom ``scenarios_dir``
    (e.g. a test fixture directory) is actually read from, not silently
    ignored in favor of the default ``scenarios/`` directory."""
    import yaml

    d = scenarios_dir / slug
    alert = json.loads((d / "alert.json").read_text(encoding="utf-8"))
    expected_path = d / "expected.yaml"
    expected = yaml.safe_load(expected_path.read_text(encoding="utf-8")) or {}
    runbook_path = d / "runbook.md"
    runbook = runbook_path.read_text(encoding="utf-8") if runbook_path.exists() else ""
    return {"alert": alert, "expected": expected, "runbook": runbook}


def scenario_pack_documents(scenarios_dir: Path | None = None) -> list[Chunk]:
    """Chunk each scenario pack's ``runbook.md`` snippet (KAN-18), tagged with
    that pack's service/incident_type/severity/environment (KAN-21).

    When ``scenarios_dir`` is ``None`` (the ``build_index()`` default), packs
    are discovered via ``backend.scenarios.loader`` against the repo's
    ``scenarios/`` directory -- unchanged from the original behavior. When
    ``scenarios_dir`` is given explicitly, packs are discovered and loaded
    directly from *that* directory instead, so the parameter is honored
    (rather than always reading the repo default) and callers/tests can point
    this at an alternate fixture directory. Either way, every pack found is
    discovered generically -- nothing here names a specific scenario. Returns
    ``[]`` (rather than raising) if the scenarios package or its optional
    dependencies (PyYAML, jsonschema) aren't available, since scenario-pack
    indexing is an addition on top of the core knowledge base, not a hard
    requirement for retrieval to work.
    """
    if scenarios_dir is None:
        try:
            from backend.scenarios.loader import list_packs, load_pack
        except Exception:  # pragma: no cover - defensive, optional dependency
            return []
        slugs = list_packs()

        def _load(slug: str) -> dict[str, Any]:
            return load_pack(slug)
    else:
        try:
            slugs = _pack_slugs_under(scenarios_dir)
        except Exception:  # pragma: no cover - defensive, unreadable directory
            return []

        def _load(slug: str) -> dict[str, Any]:
            return _load_pack_under(scenarios_dir, slug)

    chunks: list[Chunk] = []
    for slug in slugs:
        try:
            pack = _load(slug)
        except Exception:  # pragma: no cover - a malformed pack shouldn't break indexing
            continue
        alert = pack.get("alert") or {}
        expected = pack.get("expected") or {}
        runbook_text = pack.get("runbook") or ""
        if not runbook_text.strip():
            continue
        metadata = {
            "document_type": "runbook_snippet",
            "source": slug,
            "service": alert.get("service"),
            "incident_type": expected.get("agent_scenario"),
            "severity": alert.get("severity"),
            "environment": alert.get("environment"),
        }
        chunks.extend(chunk_markdown(runbook_text, source=slug, metadata=metadata))
    return chunks


def build_index(
    runbooks_dir: Path | None = None,
    embedder: Embedder | None = None,
    save_to: Path | None = None,
    include_scenario_packs: bool = False,
    scenarios_dir: Path | None = None,
) -> VectorStore:
    """Chunk + embed every runbook, returning a populated VectorStore.

    If ``save_to`` is given, the store is persisted there so it can be reloaded
    without re-embedding. If ``include_scenario_packs`` is True (KAN-21), each
    scenario pack's ``runbook.md`` snippet under ``scenarios/`` is indexed
    alongside the generic knowledge base, with metadata (service, incident_type,
    severity, environment) for filtered retrieval; default False keeps the
    original KAN-4 corpus/behavior unchanged.
    """
    runbooks_dir = runbooks_dir or default_runbooks_dir()
    embedder = embedder or HashingEmbedder()
    store = VectorStore(dim=embedder.dim, embedder_name=embedder.name)

    documents = _runbook_documents(runbooks_dir)
    if include_scenario_packs:
        documents += scenario_pack_documents(scenarios_dir)

    store.index_documents(documents, embedder)

    if save_to is not None:
        store.save(save_to)
    return store
