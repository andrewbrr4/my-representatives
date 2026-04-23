"""v2 overview output schema.

Each version owns its own Pydantic types rather than importing from a shared
module — keeps the LLM structured-output contract for this pipeline independent
of other pipelines' needs. In particular: ``bullets`` is a required
``list[str]`` here (empty list = loading state), not ``list[str] | None``.
The nullable form generated an ``anyOf[array, null]`` JSON schema that caused
Anthropic to occasionally emit ``bullets`` as a JSON-encoded string rather than
a list, failing structured-output validation.
"""

from pydantic import BaseModel, Field

from models import Citation


class ResearchSummary(BaseModel):
    bullets: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


__all__ = ["ResearchSummary"]
