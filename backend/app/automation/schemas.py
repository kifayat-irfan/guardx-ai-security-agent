"""Typed n8n webhook payloads (Phase 9).

Stable, JSON-serializable, secret-free. Severity/status are preserved
verbatim from the GuardX workflow — never invented.
"""
from datetime import datetime

from pydantic import BaseModel, Field


class N8nIncidentPayload(BaseModel):
    """Structured GuardX event sent to the n8n webhook."""

    source: str = Field(default="guardx", description="origin identifier")
    event_id: str = Field(description="GuardX event or incident id")
    event_type: str = Field(
        description="'zone_event' | 'incident' (what triggered automation)"
    )
    occurred_at: datetime | None = Field(
        default=None, description="when the underlying event happened"
    )

    # what/where
    camera_id: str | None = None
    zone_id: str | None = None
    zone_name: str | None = None
    source_event_type: str | None = Field(
        default=None, description="zone_enter | zone_exit (for zone_event)"
    )
    track_id: int | None = None
    detection_confidence: float | None = None

    # AI outcome — verbatim from the workflow, may be absent
    incident_id: str | None = None
    workflow_id: str | None = None
    status: str | None = Field(
        default=None,
        description="completed | llm_unavailable | analysis_failed | ...",
    )
    severity: str | None = Field(
        default=None,
        description="LOW | MEDIUM | HIGH | CRITICAL | None (never guessed)",
    )
    summary: str | None = None
    analysis: str | None = Field(
        default=None, description="AI reasoning, when available"
    )
    cited_policy_chunk_ids: list[str] = Field(default_factory=list)
    retrieved_policy_count: int | None = None

    reprocessed: bool = False
