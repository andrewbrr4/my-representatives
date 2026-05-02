"""Formatter node — final user-facing bullets + citation list.

One LLM call: receives the breadth pool (filtered_results) plus
depth-derived search results (depth_search_results), each typed as
``SearchResult``. Both blocks are rendered into the prompt; depth
results are tagged with the subtopic the depth subagent was investigating
so the formatter can label them. The LLM emits two parallel top-level
lists — ``bullet_texts`` and ``bullet_sources`` (URLs per bullet). Python
assembles the unified citation list from ``bullet_sources`` (URL
first-appearance order, deduped) and appends ``[N1][N2]...`` markers to
each bullet's text. The LLM never emits markers, so there's no chance
of LLM/python disagreement on N.

Schema choice: the original v4 schema was ``bullets: list[_Bullet]``
where ``_Bullet`` was a nested object. Sonnet 4.6 stringified that
nested array (returning ``bullets`` as a JSON-encoded string) on roughly
40% of runs. Flat parallel lists are the shape v2/v3 use reliably and
make stringification much rarer. Pydantic ``ValidationError`` from any
remaining wire-shape misses is handled by LangChain's standard retry
wrapper (``with_retry``).
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
from pydantic import BaseModel, Field, ValidationError

from models import Citation
from research.overview.v4.models import ResearchSummary, SearchResult
from research.overview.v4.state import V4State
from research.usage import UsageTracker

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _model_id() -> str:
    """Per-node model override for the formatter."""
    return os.getenv("OVERVIEW_V4_FORMATTER_MODEL", os.environ["CLAUDE_MODEL"])


class _FormatterOutput(BaseModel):
    """Two parallel top-level lists, indexed in lockstep.

    ``bullet_texts[i]`` is the bare one-liner; ``bullet_sources[i]`` is
    the list of supporting URLs. The model emits *only* this shape — no
    nested objects — because nested-list outputs have a high stringification
    rate on Sonnet 4.6 with the structured-output tool path.
    """

    bullet_texts: list[str] = Field(
        default_factory=list,
        description="One-liners. No [N] markers; python appends them.",
    )
    bullet_sources: list[list[str]] = Field(
        default_factory=list,
        description="Per-bullet supporting URLs. Same length as bullet_texts.",
    )


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


def _zip_bullets(
    output: _FormatterOutput,
) -> list[tuple[str, list[str]]]:
    """Pair text with sources index-wise. If lengths disagree, pad the
    shorter side: extra texts get empty sources (no citations); extra
    sources are dropped. Mismatch is logged but not fatal — we'd rather
    show the user something than fail the run."""
    texts = output.bullet_texts
    sources = output.bullet_sources
    if len(texts) != len(sources):
        logger.warning(
            f"[v4] formatter length mismatch: {len(texts)} texts vs "
            f"{len(sources)} source-lists; reconciling by truncation/pad"
        )
    pairs: list[tuple[str, list[str]]] = []
    for i, t in enumerate(texts):
        urls = sources[i] if i < len(sources) else []
        if not isinstance(urls, list):
            urls = []
        pairs.append((t, urls))
    return pairs


def _build_citations(
    pairs: list[tuple[str, list[str]]],
    pool: list[SearchResult],
) -> tuple[list[Citation], dict[str, int]]:
    """Build the unified citation list from each bullet's source URLs.

    URL first-appearance order across the bullet list. Title/published
    metadata is looked up in the combined breadth+depth pool. URLs not
    in the pool are dropped (the LLM occasionally invents plausible-looking
    URLs from training data — surfacing those to the user as citations
    would be a trust-breaker), and a warning is logged so we can monitor
    hallucination rate in traces.
    """
    by_url: dict[str, SearchResult] = {r.url: r for r in pool if r.url}
    seen: dict[str, int] = {}
    citations: list[Citation] = []
    dropped = 0
    for _text, urls in pairs:
        for url in urls:
            if not url or url in seen:
                continue
            sr = by_url.get(url)
            if sr is None:
                dropped += 1
                logger.warning(
                    f"[v4] formatter cited URL not in breadth+depth pool, dropping: {url}"
                )
                continue
            title = sr.title or url
            published = sr.published_date or None
            citations.append(Citation(title=title, url=url, published_date=published))
            seen[url] = len(citations)  # 1-indexed N
    if dropped:
        logger.info(f"[v4] formatter dropped {dropped} hallucinated URL(s)")
    return citations, seen


def _attach_markers(
    pairs: list[tuple[str, list[str]]],
    url_to_n: dict[str, int],
) -> list[str]:
    """Render each bullet as text with ``[N1][N2]...`` appended."""
    out: list[str] = []
    for text, urls in pairs:
        ns = sorted({url_to_n[u] for u in urls if u in url_to_n})
        marker = "".join(f"[{n}]" for n in ns)
        text = text.rstrip()
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
        model=_model_id(),
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )
    # Standard structured-output + retry on Pydantic validation errors. The
    # most common miss is the model stringifying one of the list fields
    # (``bullet_texts: "[\"...\"]"`` instead of ``["..."]``); on retry the
    # model usually emits the wire shape correctly.
    structured = model.with_structured_output(_FormatterOutput).with_retry(
        retry_if_exception_type=(ValidationError,),
        stop_after_attempt=2,
    )

    system_template = Template((_PROMPTS_DIR / "formatter_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "formatter_user.txt").read_text())
    system_prompt = system_template.substitute(current_date=date.today().isoformat())
    user_prompt = user_template.substitute(
        name=rep.name,
        office=rep.office,
        breadth_block=breadth_block,
        depth_block=depth_block,
    )

    # Let ValidationError propagate when both retry attempts fail. The
    # caller in pipeline.py catches it, returns (None, total), and the
    # router marks the task "failed" → frontend shows the error UI. We
    # used to swallow the exception and return an empty _FormatterOutput
    # here, but that left the store at status="complete" with bullets=[],
    # which the frontend rendered as a stuck-forever skeleton.
    result = await structured.ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "run_name": f"v4:formatter:{rep.name}",
        },
    )

    pairs = _zip_bullets(result)
    citations, url_to_n = _build_citations(pairs, filtered + depth)
    bullet_texts = _attach_markers(pairs, url_to_n)
    summary = ResearchSummary(bullets=bullet_texts, citations=citations)
    logger.info(
        f"[v4] Formatter for {rep.name}: {len(summary.bullets)} bullets / "
        f"{len(summary.citations)} citations"
    )
    return {"summary": summary, "usage_log": [usage_tracker.stats]}
