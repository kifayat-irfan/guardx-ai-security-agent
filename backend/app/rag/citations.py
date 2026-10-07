"""Citation integrity — the reasoning layer may only cite retrieved chunks.

``validate_citations(retrieved_ids, cited_ids)`` returns True iff every cited
chunk_id was actually present in the retrieval result. LangGraph (Phase 6)
will call this before accepting an AI-generated incident report.
"""
from __future__ import annotations


def validate_citations(
    retrieved_chunk_ids: set[str] | list[str],
    cited_chunk_ids: set[str] | list[str],
) -> bool:
    retrieved = set(retrieved_chunk_ids)
    cited = set(cited_chunk_ids)
    return cited <= retrieved


def invalid_citations(
    retrieved_chunk_ids: set[str] | list[str],
    cited_chunk_ids: set[str] | list[str],
) -> set[str]:
    """Return the cited IDs that were NOT retrieved (empty = all valid)."""
    return set(cited_chunk_ids) - set(retrieved_chunk_ids)
