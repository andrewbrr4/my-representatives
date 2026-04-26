"""Formatter node — final user-facing bullets + citation list.

Citation discipline (v2 lesson): the LLM emits ONLY ``bullets`` text
with ``[N]`` markers. The unified citation list is assembled in Python
from ``findings[*].source_urls`` so the structured output schema for the
LLM is the smallest possible shape (single ``list[str]``), which avoids
the Anthropic stringified-array bug.
"""

import logging
import os
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langfuse import observe
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel

from models import Citation
from research.overview._bullet_coercion import BulletList
from research.overview.v4.models import Finding, ResearchSummary, SearchResult
from research.overview.v4.state import V4State
from research.usage import UsageTracker

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class _FormatterBullets(BaseModel):
    """LLM-facing schema. Single required ``BulletList`` only — no citations,
    no ``Optional``, no nullable union. This is the v2 stringify lesson
    applied: keep the schema minimal so Anthropic doesn't emit a list as
    a string."""

    bullets: BulletList


def _build_citations(
    findings: list[Finding],
    filtered: list[SearchResult],
) -> tuple[list[Citation], dict[str, int]]:
    """Build the unified citation list from findings' source_urls.

    Order = first appearance across findings. Returns the citation list
    and a ``url -> N`` map used to render the citations block in the
    prompt.
    """
    by_url: dict[str, SearchResult] = {r.url: r for r in filtered if r.url}
    seen: dict[str, int] = {}
    citations: list[Citation] = []
    for f in findings:
        for url in f.source_urls:
            if not url or url in seen:
                continue
            sr = by_url.get(url)
            title = sr.title if sr else url
            published = sr.published_date if sr and sr.published_date else None
            citations.append(Citation(title=title, url=url, published_date=published))
            seen[url] = len(citations)  # 1-indexed N
    return citations, seen


def _format_findings_block(findings: list[Finding], url_to_n: dict[str, int]) -> str:
    if not findings:
        return "(no findings)"
    lines = []
    for i, f in enumerate(findings, start=1):
        ns = sorted({url_to_n[u] for u in f.source_urls if u in url_to_n})
        marker = "".join(f"[{n}]" for n in ns) or "[?]"
        lines.append(f"{i}. ({f.topic}) {f.claim} {marker}")
    return "\n".join(lines)


def _format_citations_block(citations: list[Citation]) -> str:
    if not citations:
        return "(none)"
    lines = []
    for i, c in enumerate(citations, start=1):
        suffix = f" (Published: {c.published_date})" if c.published_date else ""
        lines.append(f"[{i}] {c.title} — {c.url}{suffix}")
    return "\n".join(lines)


@observe(name="v4-formatter")
async def formatter(state: V4State) -> dict:
    """Format findings into bullets; assemble citations in Python."""
    rep = state["rep"]
    findings = state.get("findings") or []
    filtered = state.get("filtered_results") or []

    citations, url_to_n = _build_citations(findings, filtered)
    findings_block = _format_findings_block(findings, url_to_n)
    citations_block = _format_citations_block(citations)

    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()
    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )
    structured = model.with_structured_output(_FormatterBullets)

    system_template = Template((_PROMPTS_DIR / "formatter_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "formatter_user.txt").read_text())
    system_prompt = system_template.substitute(current_date=date.today().isoformat())
    user_prompt = user_template.substitute(
        name=rep.name,
        office=rep.office,
        findings_block=findings_block,
        citations_block=citations_block,
    )

    result = await structured.ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "run_name": f"v4:formatter:{rep.name}",
        },
    )

    summary = ResearchSummary(bullets=result.bullets, citations=citations)
    logger.info(
        f"[v4] Formatter for {rep.name}: {len(summary.bullets)} bullets / "
        f"{len(summary.citations)} citations"
    )
    return {"summary": summary, "usage_log": [usage_tracker.stats]}
