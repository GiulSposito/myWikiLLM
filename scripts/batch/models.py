"""
Pydantic v2 data models for the batch ingest pipeline.

SourceExtraction: structured output from Batch A (Haiku extraction).
PageMutationPlan: structured output from Batch B (Sonnet curation).
ResolutionDecision: structured output from Resolution Batch.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# SourceExtraction — Batch A output
# ---------------------------------------------------------------------------


class Locator(BaseModel):
    timestamp_start: str | None = None
    timestamp_end: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    speaker: str | None = None


_CLAIM_KIND_ALIASES: dict[str, str] = {
    "opportunity": "opinion",
    "recommendation": "plan",
    "insight": "opinion",
    "observation": "fact",
    "assumption": "uncertainty",
    "issue": "risk",
    "action": "plan",
    "task": "plan",
}

_VALID_CLAIM_KINDS = {
    "fact", "decision", "requirement", "constraint",
    "risk", "plan", "opinion", "uncertainty",
}


class Claim(BaseModel):
    text: str
    kind: str  # normalized by validator; unknown values mapped via _CLAIM_KIND_ALIASES
    locator: Locator
    subject_terms: list[str] = Field(default_factory=list)
    verbatim_excerpt: str | None = None

    @field_validator("kind", mode="before")
    @classmethod
    def normalize_kind(cls, v: object) -> str:
        if not isinstance(v, str):
            return "fact"
        normalized = v.lower().strip()
        if normalized in _VALID_CLAIM_KINDS:
            return normalized
        return _CLAIM_KIND_ALIASES.get(normalized, "fact")


class EntityMention(BaseModel):
    name: str
    entity_type: str  # validated/filtered by normalizer against VALID_ENTITY_TYPES
    aliases: list[str] = Field(default_factory=list)


class ConceptMention(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)


class OpenQuestion(BaseModel):
    text: str
    locator: Locator


class InternalTension(BaseModel):
    description: str
    claim_indexes: list[int] = Field(default_factory=list)

    @field_validator("claim_indexes", mode="before")
    @classmethod
    def coerce_claim_indexes(cls, v: object) -> object:
        if v is None:
            return []
        return v


class SourceExtraction(BaseModel):
    schema_version: Literal["1"] = "1"
    title: str
    authors: list[str] = Field(default_factory=list)
    source_date: str | None = None
    participants: list[str] = Field(default_factory=list)
    factual_summary: str
    claims: list[Claim] = Field(default_factory=list)
    entities: list[EntityMention] = Field(default_factory=list)
    concepts: list[ConceptMention] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    internal_tensions: list[InternalTension] = Field(default_factory=list)

    @field_validator("internal_tensions", mode="before")
    @classmethod
    def coerce_tensions_list(cls, v: object) -> object:
        if v == "" or v is None:
            return []
        return v


# ---------------------------------------------------------------------------
# ResolutionDecision — Resolution Batch output
# ---------------------------------------------------------------------------


class ResolutionDecision(BaseModel):
    action: Literal["existing", "new", "defer"]
    target_slug: str | None = None
    canonical_name: str | None = None
    alias_to_add: str | None = None
    suggested_slug: str | None = None
    confidence: Literal["high", "medium", "low"] = "medium"


# ---------------------------------------------------------------------------
# PageMutationPlan — Batch B output
# ---------------------------------------------------------------------------


class ClaimAddition(BaseModel):
    text: str
    source_slug: str
    source_claim_id: str


class RelationAddition(BaseModel):
    target_slug: str
    relation_type: str


class Conflict(BaseModel):
    conflict_type: Literal[
        "direct",
        "partial",
        "different-data",
        "divergent-interpretation",
        "stale",
    ]
    existing_claim: str
    existing_source: str | None = None
    new_claim: str
    new_source: str
    explanation: str


class PageMutationPlan(BaseModel):
    page_type: Literal["concept", "entity"]
    action: Literal["create", "update", "defer"]
    slug: str
    title: str
    aliases_to_add: list[str] = Field(default_factory=list)
    claims_to_add: list[ClaimAddition] = Field(default_factory=list)
    relations_to_add: list[RelationAddition] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    proposed_open_questions: list[str] = Field(default_factory=list)
    proposed_decisions: list[str] = Field(default_factory=list)
    # create-only fields
    abstract: str | None = None
    definition: str | None = None


# ---------------------------------------------------------------------------
# Manifest item statuses
# ---------------------------------------------------------------------------

ItemStatus = Literal[
    "scanned",
    "skipped_duplicate",
    "changed-source",
    "submitted",
    "extracted",
    "failed_extraction",
    "normalized",
    "resolved",
    "curated",
    "applied",
    "needs-review",
    "needs-replan",
]
