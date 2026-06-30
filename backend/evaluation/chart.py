"""Render a small SVG summary chart for an evaluation run (KAN-20).

A self-contained, dependency-free horizontal bar chart of per-scenario quality
scores (green = pass, red = fail), suitable for committing to ``reports/`` and
embedding as a README screenshot.
"""

from __future__ import annotations

from typing import Any

_PASS = "#2e7d32"
_FAIL = "#c62828"
_AXIS = "#9e9e9e"
_TEXT = "#212121"
_MUTED = "#616161"
_TRACK = "#eeeeee"


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def render_scores_svg(report: Any) -> str:
    """Return an SVG string charting each scenario's quality score."""
    results = report.results
    rows = len(results)
    label_w = 230
    bar_x = label_w + 20
    bar_w = 440
    row_h = 26
    top = 64
    height = top + rows * row_h + 30
    width = bar_x + bar_w + 60

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="-apple-system,Segoe UI,Roboto,sans-serif">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="16" y="26" font-size="16" font-weight="700" fill="{_TEXT}">'
        f"AI SRE Agent — diagnosis quality</text>",
        f'<text x="16" y="46" font-size="12" fill="{_MUTED}">'
        f"Pass rate {report.passed_count}/{report.total} "
        f"({report.pass_rate * 100:.0f}%) · avg score {report.average_score:.2f} · "
        f"commit {_esc(str(report.metadata.get('commit_sha', '?')))}</text>",
    ]

    # 0.6 pass-threshold guide line.
    thr_x = bar_x + 0.6 * bar_w
    parts.append(
        f'<line x1="{thr_x:.1f}" y1="{top - 6}" x2="{thr_x:.1f}" y2="{top + rows * row_h}" '
        f'stroke="{_AXIS}" stroke-dasharray="3,3" stroke-width="1"/>'
    )
    parts.append(
        f'<text x="{thr_x:.1f}" y="{top - 10}" font-size="10" fill="{_MUTED}" '
        f'text-anchor="middle">0.60 pass</text>'
    )

    for i, r in enumerate(results):
        y = top + i * row_h
        cy = y + row_h / 2
        color = _PASS if r.passed else _FAIL
        score = max(0.0, min(1.0, r.quality_score))
        parts.append(
            f'<text x="{label_w}" y="{cy + 4:.1f}" font-size="12" fill="{_TEXT}" '
            f'text-anchor="end">{_esc(r.slug)}</text>'
        )
        parts.append(
            f'<rect x="{bar_x}" y="{y + 5}" width="{bar_w}" height="{row_h - 12}" '
            f'rx="3" fill="{_TRACK}"/>'
        )
        parts.append(
            f'<rect x="{bar_x}" y="{y + 5}" width="{score * bar_w:.1f}" '
            f'height="{row_h - 12}" rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{bar_x + bar_w + 8}" y="{cy + 4:.1f}" font-size="11" '
            f'fill="{_MUTED}">{r.quality_score:.2f}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"
