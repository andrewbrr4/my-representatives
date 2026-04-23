"""Coerce stringified JSON arrays back to ``list[str]`` for LLM structured output.

Claude occasionally emits list-typed tool-use fields as a JSON-encoded
string (the whole array wrapped in one pair of quotes) instead of a real
JSON array. It happens most on long inputs with quote-heavy markdown
content. ``BulletList`` is a drop-in replacement for ``list[str]`` that
transparently parses such strings back to a list so Pydantic validation
succeeds, and logs a warning whenever it fires so the rate stays visible.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from pydantic import BeforeValidator

logger = logging.getLogger(__name__)


def _coerce_stringified_bullets(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return value
    if isinstance(parsed, list):
        logger.warning(
            "Coerced stringified JSON array to list[str] (len=%d); "
            "LLM emitted a list field as a string.",
            len(parsed),
        )
        return parsed
    return value


BulletList = Annotated[list[str], BeforeValidator(_coerce_stringified_bullets)]
