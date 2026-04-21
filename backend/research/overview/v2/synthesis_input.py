"""Build the synthesis-step input: dossier text + unified citation pool.

The synthesis LLM sees one blob of text grouped by section with renumbered
``[N]`` markers, plus a single merged citation list. This keeps the synthesis
prompt small and its citation indexing unambiguous.
"""

import re
from dataclasses import dataclass

from models import Citation

_MARKER_PATTERN = re.compile(r"\[(\d+)\]")


@dataclass
class DossierResult:
    dossier: str
    unified_citations: list[Citation]


def _renumber_markers(item: str, offset: int) -> str:
    """Rewrite ``[N]`` → ``[N+offset]`` in one bullet string."""

    def _sub(match: re.Match[str]) -> str:
        n = int(match.group(1))
        return f"[{n + offset}]"

    return _MARKER_PATTERN.sub(_sub, item)


def build_dossier(
    sections: list[tuple[str, list[str], list[Citation]]],
) -> DossierResult:
    """Merge per-section items/citations into one dossier blob + unified list.

    ``sections`` is an ordered list of ``(section_name, items, citations)``.
    Sections with no items are skipped entirely. Inline ``[N]`` markers in
    items are rewritten so they point at 1-indexed positions in the returned
    ``unified_citations`` list.
    """
    unified: list[Citation] = []
    blocks: list[str] = []

    for section_name, items, citations in sections:
        if not items:
            continue
        offset = len(unified)
        renumbered_items = [_renumber_markers(item, offset) for item in items]
        unified.extend(citations)

        lines = [f"## {section_name}"]
        lines.extend(f"- {item}" for item in renumbered_items)
        if citations:
            lines.append("")
            lines.append("Sources:")
            lines.extend(
                f"[{offset + i + 1}] {c.url}" for i, c in enumerate(citations)
            )
        blocks.append("\n".join(lines))

    return DossierResult(
        dossier="\n\n".join(blocks),
        unified_citations=unified,
    )
