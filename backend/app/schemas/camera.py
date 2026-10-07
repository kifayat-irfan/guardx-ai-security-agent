"""Camera schemas (Phase 1: shapes only; CRUD arrives Phase 2+)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CameraCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source_type: str = Field(pattern="^(file|rtsp|webcam)$")
    source_url: str = Field(min_length=1)


class CameraRead(BaseModel):
    id: uuid.UUID
    name: str
    source_type: str
    source_url: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
