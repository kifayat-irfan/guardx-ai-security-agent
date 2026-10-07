"""Incident workflow schemas — structured decision, no persistence (Phase 7)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class IncidentDecision(BaseModel):
    workflow_id: str
    event_id: str
    status: str = Field(
        description="completed | invalid_event | retrieval_failed | "
                    "no_policies | llm_unavailable | analysis_failed | "
                    "citation_invalid"
    )
    summary: str | None = None
    severity: str | None = Field(
        default=None, description="LOW | MEDIUM | HIGH | CRITICAL"
    )
    recommended_action: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    cited_policy_chunk_ids: list[str] = Field(default_factory=list)
    retrieved_policy_count: int = 0
    error: dict | None = Field(
        default=None, description="{node, code, message} on failure"
    )
    started_at: str
    finished_at: str
    duration_ms: float


class WorkflowSummary(BaseModel):
    workflow_id: str
    status: str
    current_node: str | None = None
    started_at: str
    finished_at: str | None = None
    error: dict | None = None
    decision: IncidentDecision | None = None
