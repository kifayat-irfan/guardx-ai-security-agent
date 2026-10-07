"""Zone schemas (Phase 1: shapes only; CRUD arrives Phase 3)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ZoneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    polygon: list[list[float]] = Field(min_length=3)
    dwell_seconds: float = Field(default=2.0, ge=0)
    cooldown_seconds: float = Field(default=60.0, ge=0)
    active: bool = True


class ZoneRead(BaseModel):
    id: uuid.UUID
    camera_id: uuid.UUID
    name: str
    polygon: list[list[float]]
    dwell_seconds: float
    cooldown_seconds: float
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
