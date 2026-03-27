"""Shared configuration helpers for research routers."""

import os
from decimal import Decimal


def cost_config() -> dict:
    """Read cost-tracking env vars once per research task."""
    input_cost_env = os.environ.get("ANTHROPIC_INPUT_COST_PER_M")
    output_cost_env = os.environ.get("ANTHROPIC_OUTPUT_COST_PER_M")
    search_cost_env = os.environ.get("COST_PER_SEARCH")
    return {
        "model": os.environ.get("CLAUDE_MODEL"),
        "input_cost_per_m": Decimal(input_cost_env) if input_cost_env else None,
        "output_cost_per_m": Decimal(output_cost_env) if output_cost_env else None,
        "search_tool": os.environ.get("SEARCH_TOOL", "tavily"),
        "cost_per_search": Decimal(search_cost_env) if search_cost_env else None,
        "environment": os.environ.get("ENVIRONMENT", "dev"),
    }
