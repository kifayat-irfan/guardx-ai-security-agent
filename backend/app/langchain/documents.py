"""GuardX <-> LangChain document conversion.

Every conversion preserves the full GuardX metadata, especially the
deterministic ``chunk_id`` — the citation anchor for Phase 6.
"""
from __future__ import annotations

from langchain_core.documents import Document

from app.rag.schemas import RetrievedChunk

METADATA_KEYS = (
    "chunk_id",
    "policy_id",
    "policy_title",
    "section",
    "category",
    "version",
    "source",
    "score",
)


def retrieved_chunk_to_document(chunk: RetrievedChunk) -> Document:
    """Convert a GuardX RetrievedChunk into a LangChain Document."""
    return Document(
        page_content=chunk.content,
        metadata={
            "chunk_id": chunk.chunk_id,
            "policy_id": chunk.policy_id,
            "policy_title": chunk.policy_title,
            "section": chunk.section,
            "category": chunk.metadata.get("category", ""),
            "version": chunk.metadata.get("version", ""),
            "source": chunk.metadata.get("source", ""),
            "score": chunk.score,
        },
    )


def document_to_chunk_summary(doc: Document) -> dict:
    """Inverse view: the GuardX-relevant fields of a LangChain Document."""
    md = doc.metadata or {}
    return {
        "chunk_id": md.get("chunk_id"),
        "policy_id": md.get("policy_id"),
        "policy_title": md.get("policy_title"),
        "section": md.get("section"),
        "score": md.get("score"),
        "content": doc.page_content,
    }
