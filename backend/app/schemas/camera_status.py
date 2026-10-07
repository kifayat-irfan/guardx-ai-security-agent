"""Camera runtime status schema (vision loop state)."""
import uuid

from pydantic import BaseModel

from app.vision.detector import Detection


class CameraUpdate(BaseModel):
    name: str | None = None
    source_type: str | None = None
    source_url: str | None = None


class CameraStatus(BaseModel):
    camera_id: uuid.UUID
    status: str  # streaming | idle | error
    fps: float
    person_count: int
    frame_index: int
    inference_ms: float
    error: str | None = None
    detections: list[Detection] = []
