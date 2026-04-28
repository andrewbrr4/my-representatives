"""Formatter node — final user-facing bullets + citation list.

One LLM call: receives the breadth pool (filtered_results) plus
depth-derived search results (depth_search_results), each typed as
``SearchResult``. Both blocks are rendered into the prompt; depth
results are tagged with the subtopic the depth subagent was investigating
so the formatter can label them. The LLM emits per-bullet bare text +
its source URLs. Python assembles the unified citation list from
``bullets[*].source_urls`` (URL first-appearance order, deduped) and
appends ``[N1][N2]...`` markers to each bullet's text. The LLM never
emits markers, so there's no chance of LLM/python disagreement on N.
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
from pydantic import BaseModel, Field

from models import Citation
from research.overview.v4.models import ResearchSummary, SearchResult
from research.overview.v4.state import V4State
from research.usage import UsageTracker

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class _Bullet(BaseModel):
    """One bullet emitted by the formatter LLM. Bare text, no [N] markers
    — python appends those after assembling the unified citation list."""

    text: str = Field(description="One-liner. No [N] citation markers.")
    source_urls: list[str] = Field(
        default_factory=list,
        description="URLs supporting this bullet, drawn from the materials.",
    )


class _FormatterOutput(BaseModel):
    bullets: list[_Bullet] = Field(default_factory=list)


def _format_breadth_block(results: list[SearchResult]) -> str:
    if not results:
        return "(no breadth results)"
    lines = []
    for i, r in enumerate(results, start=1):
        date_suffix = f"  Published: {r.published_date}\n" if r.published_date else ""
        lines.append(
            f"[{i}] {r.title}\n  URL: {r.url}\n{date_suffix}  {r.snippet}"
        )
    return "\n\n".join(lines)


def _format_depth_block(results: list[SearchResult]) -> str:
    if not results:
        return "(no depth results)"
    # Group by topic so the formatter can see which subtopic each
    # depth result was sourced from.
    by_topic: dict[str, list[SearchResult]] = {}
    for r in results:
        by_topic.setdefault(r.topic or "(untagged)", []).append(r)
    lines = []
    for topic, group in by_topic.items():
        lines.append(f"### Topic: {topic}")
        for r in group:
            date_suffix = f" (Published: {r.published_date})" if r.published_date else ""
            lines.append(f"- {r.title}{date_suffix} — {r.url}")
            lines.append(f"  {r.snippet}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _build_citations(
    bullets: list[_Bullet],
    pool: list[SearchResult],
) -> tuple[list[Citation], dict[str, int]]:
    """Build the unified citation list from each bullet's source_urls.

    URL first-appearance order across the bullet list. Title/published
    metadata is looked up in the combined breadth+depth pool. Unknown
    URLs (cited by the LLM but not in the pool) fall back to URL-as-title
    and a warning is logged.
    """
    by_url: dict[str, SearchResult] = {r.url: r for r in pool if r.url}
    seen: dict[str, int] = {}
    citations: list[Citation] = []
    for b in bullets:
        for url in b.source_urls:
            if not url or url in seen:
                continue
            sr = by_url.get(url)
            if sr:
                title = sr.title or url
                published = sr.published_date or None
            else:
                title = url
                published = None
                logger.warning(
                    f"[v4] formatter cited URL not found in breadth or depth pool: {url}"
                )
            citations.append(Citation(title=title, url=url, published_date=published))
            seen[url] = len(citations)  # 1-indexed N
    return citations, seen


def _attach_markers(bullets: list[_Bullet], url_to_n: dict[str, int]) -> list[str]:
    """Render each bullet as text with ``[N1][N2]...`` appended."""
    out: list[str] = []
    for b in bullets:
        ns = sorted({url_to_n[u] for u in b.source_urls if u in url_to_n})
        marker = "".join(f"[{n}]" for n in ns)
        text = b.text.rstrip()
        out.append(f"{text} {marker}".rstrip() if marker else text)
    return out


@observe(name="v4-formatter")
async def formatter(state: V4State) -> dict:
    """Format breadth + depth search results into bullets; assemble
    citations in python."""
    rep = state["rep"]
    filtered = state.get("filtered_results") or []
    depth = state.get("depth_search_results") or []

    breadth_block = _format_breadth_block(filtered)
    depth_block = _format_depth_block(depth)

    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()
    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )
    structured = model.with_structured_output(_FormatterOutput)

    system_template = Template((_PROMPTS_DIR / "formatter_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "formatter_user.txt").read_text())
    system_prompt = system_template.substitute(current_date=date.today().isoformat())
    user_prompt = user_template.substitute(
        name=rep.name,
        office=rep.office,
        breadth_block=breadth_block,
        depth_block=depth_block,
    )

    result = await structured.ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "run_name": f"v4:formatter:{rep.name}",
        },
    )

    citations, url_to_n = _build_citations(result.bullets, filtered + depth)
    bullet_texts = _attach_markers(result.bullets, url_to_n)
    summary = ResearchSummary(bullets=bullet_texts, citations=citations)
    logger.info(
        f"[v4] Formatter for {rep.name}: {len(summary.bullets)} bullets / "
        f"{len(summary.citations)} citations"
    )
    return {"summary": summary, "usage_log": [usage_tracker.stats]}
