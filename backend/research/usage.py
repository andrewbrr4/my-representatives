"""Lightweight callback handler for tracking LLM token usage and tool calls.

Fully independent of Langfuse — if Langfuse breaks, this still works.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult


@dataclass
class UsageStats:
    """Aggregated usage for one or more agents."""

    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0

    def __iadd__(self, other: "UsageStats") -> "UsageStats":
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.tool_calls += other.tool_calls
        return self

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class UsageTracker(AsyncCallbackHandler):
    """Tracks token usage and tool calls during a LangChain agent run."""

    def __init__(self) -> None:
        self.stats = UsageStats()

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        for generations in response.generations:
            for gen in generations:
                meta = getattr(gen, "message", None)
                if meta is None:
                    continue
                usage = getattr(meta, "usage_metadata", None) or {}
                self.stats.input_tokens += usage.get("input_tokens", 0)
                self.stats.output_tokens += usage.get("output_tokens", 0)

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self.stats.tool_calls += 1
