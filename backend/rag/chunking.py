"""Markdown chunking (KAN-4).

Splits a runbook into section-aware chunks: text is grouped under its nearest
Markdown heading, and long sections are further split by a soft token budget so
each chunk is retrievable on its own while keeping its heading for citation.
"""

from __future__ import annotations

import re
from pathlib import Path

from backend.rag.models import Chunk

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def chunk_markdown(text: str, source: str, max_words: int = 120) -> list[Chunk]:
    """Chunk Markdown ``text`` from ``source`` into heading-scoped pieces."""
    chunks: list[Chunk] = []
    heading = "Overview"
    buffer: list[str] = []
    seq = 0

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
                Chunk(id=chunk_id, source=source, heading=heading, text=piece)
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


def chunk_file(path: Path, max_words: int = 120) -> list[Chunk]:
    """Chunk a Markdown file on disk."""
    return chunk_markdown(path.read_text(encoding="utf-8"), path.name, max_words)
