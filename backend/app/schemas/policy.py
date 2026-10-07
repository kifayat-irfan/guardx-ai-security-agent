"""Policy schemas (Phase 1: shapes only; RAG arrives Phase 4)."""
import uuid
from datetime import datetime

from pydantic import BaseModel


class PolicyRead(BaseModel):
    id: uuid.UUID
    title: str
    category: str
    version: str
    updated_at: datetime

    model_config = {"from_attributes": True}
