"""v3 overview output schema.

Each version owns its own Pydantic types. ``bullets`` is a required
``list[str]`` (empty list = loading state) to avoid the
``list[str] | None`` → ``anyOf[array, null]`` JSON schema that triggers
Anthropic to occasionally emit the array as a JSON-encoded string.
"""

from pydantic import BaseModel, Field

from models import Citation
from research.overview._bullet_coercion import BulletList


class ResearchSummary(BaseModel):
    bullets: BulletList = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


__all__ = ["ResearchSummary"]
