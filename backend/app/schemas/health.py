"""Health-check schemas."""
from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str
    version: str


class ComponentStatus(BaseModel):
    status: str  # up | down | unavailable | initializing | ready | error
    detail: str | None = None


class DetailedHealth(BaseModel):
    status: str  # ok | degraded
    version: str
    postgres: ComponentStatus
    chromadb: ComponentStatus  # Phase 4: local RAG/ChromaDB subsystem state
    yolo: ComponentStatus  # Phase 2: reports model-loaded state
