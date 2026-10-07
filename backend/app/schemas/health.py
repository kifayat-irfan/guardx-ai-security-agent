"""Health-check schemas."""
from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str
    version: str


class ComponentStatus(BaseModel):
    status: str  # up | down
    detail: str | None = None


class DetailedHealth(BaseModel):
    status: str  # ok | degraded
    version: str
    postgres: ComponentStatus
    chromadb: ComponentStatus
    yolo: ComponentStatus  # Phase 2: reports model-loaded state
