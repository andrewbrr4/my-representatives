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

import json
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
from research.overview.models import ResearchSummary, SearchResult, SourceLink
from research.overview.progress import report_step
from research.overview.state import V4State
from store.research_store import InMemoryResearchStore
from research.usage import UsageTracker

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _show_sources_enabled() -> bool:
    """Gate for the show-sources feature: pre-formatter dedup + ``sources``
    pass-through on the summary. Read at call time so tests/env flips don't
    require a restart."""
    return os.getenv("OVERVIEW_V4_SHOW_SOURCES", "").strip().lower() in (
        "1", "true", "yes", "on"
    )


def _dedupe_depth_against_breadth(
    breadth: list[SearchResult],
    depth: list[SearchResult],
) -> list[SearchResult]:
    """Drop depth results whose URL already appears in breadth or earlier
    in depth. Preserves topic tags on the surviving depth results."""
    seen: set[str] = {r.url for r in breadth if r.url}
    out: list[SearchResult] = []
    for r in depth:
        if not r.url or r.url in seen:
            continue
        seen.add(r.url)
        out.append(r)
    return out


def _build_sources(pool: list[SearchResult]) -> list[SourceLink]:
    """Project the combined pool to ``SourceLink`` items, deduping by URL
    in first-occurrence order. Drops entries with no URL or no title."""
    seen: set[str] = set()
    out: list[SourceLink] = []
    for r in pool:
        if not r.url or not r.title or r.url in seen:
            continue
        seen.add(r.url)
        out.append(SourceLink(title=r.title, url=r.url))
    return out


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


def _streaming_enabled() -> bool:
    """Default ON — streaming is the intended formatter experience. Flip the
    env var to ``false`` to fall back to the structured-output path."""
    return os.getenv("OVERVIEW_V4_FORMATTER_STREAMING", "true").strip().lower() in (
        "1", "true", "yes", "on"
    )


def _min_bullets() -> int:
    return int(os.getenv("OVERVIEW_V4_FORMATTER_MIN_BULLETS", "3"))


async def _handle_line(
    line: str,
    *,
    pool_by_url: dict[str, SearchResult],
    bullets: list[str],
    citations: list[Citation],
    url_to_n: dict[str, int],
    sources: list[SourceLink],
    store: InMemoryResearchStore | None,
    research_id: str | None,
) -> bool:
    """Parse one NDJSON line, append a bullet + citations, write a partial.

    Mutates ``bullets`` / ``citations`` / ``url_to_n`` in place. Returns True
    if a bullet was appended, False if the line was skipped (blank, malformed
    JSON, or wrong shape). URLs not in ``pool_by_url`` are dropped (logged) —
    same hallucination-drop philosophy as the structured path.
    """
    line = line.strip()
    if not line:
        return False
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        logger.warning(f"[v4] formatter stream: skipping malformed line: {line[:120]}")
        return False
    if not isinstance(obj, dict):
        logger.warning("[v4] formatter stream: skipping non-object line")
        return False
    text = obj.get("text")
    srcs = obj.get("sources")
    if not isinstance(text, str) or not text.strip() or not isinstance(srcs, list):
        logger.warning("[v4] formatter stream: skipping bad-shape line")
        return False

    for url in srcs:
        if not isinstance(url, str) or not url or url in url_to_n:
            continue
        sr = pool_by_url.get(url)
        if sr is None:
            logger.warning(f"[v4] formatter stream cited URL not in pool, dropping: {url}")
            continue
        citations.append(
            Citation(title=sr.title or url, url=url, published_date=sr.published_date or None)
        )
        url_to_n[url] = len(citations)  # 1-indexed N

    ns = sorted({url_to_n[u] for u in srcs if isinstance(u, str) and u in url_to_n})
    marker = "".join(f"[{n}]" for n in ns)
    text = text.strip()
    bullets.append(f"{text} {marker}".rstrip() if marker else text)

    if store is not None and research_id is not None:
        await store.update_partial(
            research_id,
            ResearchSummary(
                bullets=list(bullets), citations=list(citations), sources=sources
            ),
        )
    return True


async def _consume_stream(
    content_iter,
    *,
    pool_by_url: dict[str, SearchResult],
    sources: list[SourceLink],
    store: InMemoryResearchStore | None,
    research_id: str | None,
) -> ResearchSummary:
    """Drive the NDJSON line loop over an async iterator of content strings.

    Buffers partial lines across chunks; drains a trailing unterminated line
    at the end. Returns the final ResearchSummary.
    """
    line_buffer = ""
    bullets: list[str] = []
    citations: list[Citation] = []
    url_to_n: dict[str, int] = {}
    n_chunks = 0

    async for content in content_iter:
        n_chunks += 1
        line_buffer += content if isinstance(content, str) else str(content)
        while "\n" in line_buffer:
            line, line_buffer = line_buffer.split("\n", 1)
            await _handle_line(
                line, pool_by_url=pool_by_url, bullets=bullets, citations=citations,
                url_to_n=url_to_n, sources=sources, store=store, research_id=research_id,
            )
    if line_buffer.strip():
        await _handle_line(
            line_buffer, pool_by_url=pool_by_url, bullets=bullets, citations=citations,
            url_to_n=url_to_n, sources=sources, store=store, research_id=research_id,
        )

    logger.info(f"[v4] Formatter streamed {len(bullets)} bullets in {n_chunks} chunks")
    return ResearchSummary(bullets=bullets, citations=citations, sources=sources)


async def _formatter_streaming(state: V4State) -> dict:
    """NDJSON line-streaming formatter: emits bullets to the store as they
    land via update_partial(). Falls back to RuntimeError (-> task fail) if
    fewer than _min_bullets() valid bullets are produced."""
    rep = state["rep"]
    filtered = state.get("filtered_results") or []
    depth = state.get("depth_search_results") or []
    store = state.get("store")
    research_id = state.get("research_id")

    show_sources = _show_sources_enabled()
    if show_sources:
        before = len(depth)
        depth = _dedupe_depth_against_breadth(filtered, depth)
        logger.info(
            f"[v4] Formatter dedupe (show-sources on): depth {before} -> {len(depth)}"
        )

    breadth_block = _format_breadth_block(filtered)
    depth_block = _format_depth_block(depth)
    pool = filtered + depth
    pool_by_url = {r.url: r for r in pool if r.url}
    sources = _build_sources(pool) if show_sources else []

    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()
    model = ChatAnthropic(
        model=_model_id(),
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )

    system_template = Template((_PROMPTS_DIR / "formatter_system_streaming.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "formatter_user_streaming.txt").read_text())
    system_prompt = system_template.substitute(current_date=date.today().isoformat())
    user_prompt = user_template.substitute(
        name=rep.name,
        office=rep.office,
        breadth_block=breadth_block,
        depth_block=depth_block,
    )

    async def _content_iter():
        async for chunk in model.astream(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
            config={
                "callbacks": [langfuse_handler, usage_tracker],
                "run_name": f"v4:formatter:{rep.name}",
            },
        ):
            content = chunk.content
            if isinstance(content, str):
                yield content
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, str):
                        yield block
                    elif isinstance(block, dict) and block.get("type") == "text":
                        yield block.get("text", "")

    summary = await _consume_stream(
        _content_iter(),
        pool_by_url=pool_by_url,
        sources=sources,
        store=store,
        research_id=research_id,
    )

    if len(summary.bullets) < _min_bullets():
        raise RuntimeError(
            f"formatter produced too few valid bullets: {len(summary.bullets)}"
        )

    logger.info(
        f"[v4] Formatter (streaming) for {rep.name}: {len(summary.bullets)} bullets / "
        f"{len(summary.citations)} citations / {len(summary.sources)} sources"
    )
    return {"summary": summary, "usage_log": [usage_tracker.stats]}


@observe(name="v4-formatter")
async def formatter(state: V4State) -> dict:
    """Dispatch: report the formatter step, then stream or use structured output."""
    await report_step(state, "formatter")
    if _streaming_enabled():
        return await _formatter_streaming(state)
    return await _formatter_structured(state)


async def _formatter_structured(state: V4State) -> dict:
    """Format breadth + depth search results into bullets; assemble
    citations in python. (Structured-output path — the streaming fallback.)"""
    rep = state["rep"]
    filtered = state.get("filtered_results") or []
    depth = state.get("depth_search_results") or []

    show_sources = _show_sources_enabled()
    if show_sources:
        before = len(depth)
        depth = _dedupe_depth_against_breadth(filtered, depth)
        logger.info(
            f"[v4] Formatter dedupe (show-sources on): depth {before} → "
            f"{len(depth)} after dropping URL collisions with breadth/depth"
        )

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
    sources = _build_sources(filtered + depth) if show_sources else []
    summary = ResearchSummary(
        bullets=bullet_texts, citations=citations, sources=sources
    )
    logger.info(
        f"[v4] Formatter for {rep.name}: {len(summary.bullets)} bullets / "
        f"{len(summary.citations)} citations / {len(summary.sources)} sources"
    )
    return {"summary": summary, "usage_log": [usage_tracker.stats]}
