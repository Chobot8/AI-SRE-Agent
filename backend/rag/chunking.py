"""Markdown chunking (KAN-4, extended KAN-21).

Splits a runbook into section-aware chunks: text is grouped under its nearest
Markdown heading, and long sections are further split by a soft token budget so
each chunk is retrievable on its own while keeping its heading for citation.

KAN-21: chunks can optionally carry a metadata dict (service, incident_type,
severity, environment, document_type, source) so retrieval can filter on it.
The ``metadata`` parameter defaults to ``None`` (-> ``{}``), so existing calls
are unaffected.
"""

from __future__ import annotations

import re
from pathlib import Path

from backend.rag.models import Chunk

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def chunk_markdown(
    text: str,
    source: str,
    max_words: int = 120,
    metadata: dict | None = None,
) -> list[Chunk]:
    """Chunk Markdown ``text`` from ``source`` into heading-scoped pieces.

    ``metadata`` (KAN-21), when given, is attached to every chunk produced —
    e.g. ``{"document_type": "runbook", "incident_type": "high_latency"}``.
    """
    chunks: list[Chunk] = []
    heading = "Overview"
    buffer: list[str] = []
    seq = 0
    meta = dict(metadata) if metadata else {}

    def flush() -> None:
        nonlocal seq, buffer
        body = "\n".join(buffer).strip()
        buffer = []
        if not body:
            return
        words = body.split()
        # Split overly long sections by the word budget.
        for start in range(0, len(words), max_words):
            piece = " ".join(words[start : start + max_words])
            chunk_id = f"{source}::{_slug(heading)}::{seq}"
            chunks.append(
                Chunk(id=chunk_id, source=source, heading=heading, text=piece, metadata=dict(meta))
            )
            seq += 1

    for line in text.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            flush()
            heading = m.group(2).strip()
            continue
        buffer.append(line)
    flush()
    return chunks


def chunk_file(path: Path, max_words: int = 120, metadata: dict | None = None) -> list[Chunk]:
    """Chunk a Markdown file on disk."""
    return chunk_markdown(path.read_text(encoding="utf-8"), path.name, max_words, metadata=metadata)
