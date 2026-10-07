"""RAG typed schemas — retrieval only, no decisions."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PolicyMeta(BaseModel):
    policy_id: str
    title: str
    version: str
    effective_date: str
    category: str
    source: str  # filename under policies/


class PolicyChunk(BaseModel):
    chunk_id: str = Field(
        description="deterministic: '<policy_id>#<section-slug>'"
    )
    policy_id: str
    policy_title: str
    section: str
    category: str = ""
    version: str
    source: str
    content: str


class PolicySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=3, ge=1, le=20)
    policy_id: str | None = Field(
        default=None, description="optional metadata filter"
    )
    category: str | None = Field(
        default=None, description="optional metadata filter"
    )


class RetrievedChunk(BaseModel):
    chunk_id: str
    policy_id: str
    policy_title: str
    section: str
    content: str
    score: float = Field(description="relevance 0-1, higher is better")
    metadata: dict


class PolicySearchResult(BaseModel):
    query: str
    top_k: int
    chunks: list[RetrievedChunk]
    took_ms: float


class PolicyCitation(BaseModel):
    """A citation the (future) reasoning layer wants to use."""

    chunk_id: str
    policy_id: str
    quote: str = ""


class IndexReport(BaseModel):
    indexed_documents: int
    indexed_chunks: int
    collection: str
    embedding_model: str
    duration_ms: float
    indexed_at: datetime = Field(default_factory=datetime.utcnow)


class RagStatus(BaseModel):
    state: str  # unavailable | initializing | ready | error
    detail: str | None = None
    collection: str | None = None
    chunk_count: int = 0
    embedding_model: str | None = None
