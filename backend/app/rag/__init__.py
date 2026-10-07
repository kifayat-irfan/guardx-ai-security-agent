"""RAG: local policy retrieval (ChromaDB + sentence-transformers).

Retrieval only — it never makes security decisions. LangGraph (Phase 6)
consumes the retrieved policies.
"""
from app.rag.citations import invalid_citations, validate_citations  # noqa: F401
from app.rag.event_query import describe_event, zone_event_to_query  # noqa: F401
from app.rag.schemas import (  # noqa: F401
    IndexReport,
    PolicyChunk,
    PolicyCitation,
    PolicyMeta,
    PolicySearchRequest,
    PolicySearchResult,
    RagStatus,
    RetrievedChunk,
)
from app.rag.service import PolicyRAGService, get_rag_service  # noqa: F401
