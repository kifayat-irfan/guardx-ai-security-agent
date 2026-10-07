"""Structured output schemas for the future AI reasoning step (Phase 6).

SecurityAnalysis is preparation only: the LangChain layer never persists a
final incident. LangGraph will produce and validate these.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityAnalysis(BaseModel):
    """Structured security analysis — produced by the LLM in Phase 6."""

    summary: str = Field(
        min_length=1, description="one-paragraph factual summary of the event"
    )
    severity: Severity
    recommended_action: str = Field(
        min_length=1,
        description="concrete next step drawn from the cited policies",
    )
    cited_policy_chunk_ids: list[str] = Field(
        default_factory=list,
        description="chunk_ids actually retrieved (validated by citations)",
    )
    reasoning: str = Field(
        default="",
        description="why this severity/action, distinguishing facts from recommendations",
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="model self-confidence 0-1"
    )

    @field_validator("cited_policy_chunk_ids")
    @classmethod
    def _non_empty_ids(cls, v: list[str]) -> list[str]:
        for cid in v:
            if not cid or not cid.strip():
                raise ValueError("cited chunk ids must be non-empty strings")
        return v

    model_config = {"use_enum_values": True}
