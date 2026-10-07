"""IncidentState — the LangGraph state (JSON-serializable only).

No arbitrary Python objects: documents are stored as plain dicts, the event
as a JSON-mode dict. This keeps the state loggable, inspectable, and
persistable later.
"""
from __future__ import annotations

from typing import TypedDict


class IncidentState(TypedDict, total=False):
    # identity / lifecycle
    workflow_id: str
    status: str  # running | completed | invalid_event | retrieval_failed |
                 # no_policies | llm_unavailable | analysis_failed |
                 # citation_invalid
    current_node: str
    error: dict  # {node, code, message}
    started_at: str
    finished_at: str
    timings_ms: dict  # {node: ms}

    # event
    event: dict  # ZoneEvent.model_dump(mode="json")

    # retrieval
    policy_query: str
    retrieved_policies: list[dict]  # [{chunk_id, policy_id, policy_title,
                                    #   section, content, score}]
    retrieved_chunk_ids: list[str]
    retrieval_ok: bool

    # analysis
    analysis_raw: str | None
    analysis: dict | None  # SecurityAnalysis.model_dump()

    # decision
    decision: dict | None  # IncidentDecision.model_dump()


TERMINAL_STATUSES = frozenset({
    "completed", "invalid_event", "retrieval_failed", "no_policies",
    "llm_unavailable", "analysis_failed", "citation_invalid",
})
