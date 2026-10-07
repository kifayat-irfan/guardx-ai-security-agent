"""Zone event schemas — the engine's only output.

The engine NEVER creates security incidents; it emits these structured
events for Phase 4+ (RAG / LangGraph) to consume.
"""
from __future__ import annotations

import uuid
from enum import Enum

from pydantic import BaseModel, Field


class ZoneEventType(str, Enum):
    ZONE_ENTER = "zone_enter"
    ZONE_EXIT = "zone_exit"


class ZoneEvent(BaseModel):
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    camera_id: uuid.UUID
    zone_id: uuid.UUID
    zone_name: str
    tracking_id: int
    event_type: ZoneEventType
    timestamp: float = Field(description="seconds since source opened (frame time)")
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: list[float] = Field(description="xyxy in normalized 0-1 coords")
    point: list[float] = Field(
        description="bottom-center reference point, normalized 0-1 [x, y]"
    )
    metadata: dict = Field(
        default_factory=dict,
        description="dwell_elapsed, cooldown_remaining, zone config snapshot",
    )

    model_config = {"use_enum_values": True}
