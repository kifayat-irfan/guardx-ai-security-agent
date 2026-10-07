"""Incident workflow schemas — structured decision + persistence (Phase 7)."""
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

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
    incident_id: str | None = Field(
        default=None, description="persisted incident id (Phase 7)"
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


# -- persistence (Phase 7) ---------------------------------------------------


class IncidentOut(BaseModel):
    id: uuid_mod.UUID
    external_event_id: str
    camera_id: uuid_mod.UUID
    zone_id: uuid_mod.UUID
    zone_name: str
    tracking_id: int
    event_type: str
    occurred_at: datetime
    detection_confidence: float
    bounding_box: list
    point: list
    event_data: dict
    status: str
    severity: str | None
    summary: str | None
    recommended_action: str | None
    analysis_confidence: float | None
    error: dict | None
    workflow_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IncidentReportOut(BaseModel):
    id: uuid_mod.UUID
    incident_id: uuid_mod.UUID
    report_type: str
    title: str
    summary: str | None
    severity: str | None
    recommended_action: str | None
    reasoning: str | None
    cited_policy_chunk_ids: list[str]
    retrieved_policy_count: int
    retrieved_chunk_ids: list[str]
    generated_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentDetail(BaseModel):
    incident: IncidentOut
    report: IncidentReportOut | None


class IncidentList(BaseModel):
    items: list[IncidentOut]
    page: int
    page_size: int
    total: int
    total_pages: int
