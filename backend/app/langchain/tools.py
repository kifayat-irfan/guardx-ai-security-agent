"""LangChain tool: retrieve_security_policy.

Retrieval only — the tool returns policy chunks; it never makes a security
decision. Phase 6 (LangGraph) will call this tool during incident analysis.
"""
from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.langchain.documents import document_to_chunk_summary
from app.langchain.retriever import GuardXPolicyRetriever
from app.rag.event_query import zone_event_to_query
from app.zone_engine.events import ZoneEvent


class PolicyToolInput(BaseModel):
    event_description: str = Field(
        description="natural-language description of the security event"
    )
    zone_name: str | None = Field(
        default=None, description="restricted zone name, if known"
    )
    event_type: str | None = Field(
        default=None, description="zone_enter | zone_exit, if known"
    )
    camera_id: str | None = Field(
        default=None, description="camera context, if known"
    )
    top_k: int = Field(default=3, ge=1, le=10)


def build_policy_tool(retriever: GuardXPolicyRetriever) -> StructuredTool:
    """Build the retrieve_security_policy tool around a retriever."""

    def _run(
        event_description: str,
        zone_name: str | None = None,
        event_type: str | None = None,
        camera_id: str | None = None,
        top_k: int = 3,
    ) -> dict:
        query = event_description.strip()
        if zone_name and zone_name.lower() not in query.lower():
            query = f"{query} Zone: {zone_name}."
        retriever.top_k = max(1, min(10, top_k))
        docs = retriever.invoke(query)
        return {
            "query": query,
            "zone_name": zone_name,
            "event_type": event_type,
            "camera_id": camera_id,
            "chunks": [document_to_chunk_summary(d) for d in docs],
            "retrieved_chunk_ids": [
                d.metadata.get("chunk_id") for d in docs
            ],
        }

    return StructuredTool.from_function(
        func=_run,
        name="retrieve_security_policy",
        description=(
            "Retrieve the security policy sections relevant to a security "
            "event. Input an event description (optionally with zone name, "
            "event type, camera). Returns ranked policy chunks with chunk "
            "IDs for citation. This tool retrieves information only; it "
            "does not decide severity or response."
        ),
        args_schema=PolicyToolInput,
    )


def zone_event_tool_input(event: ZoneEvent) -> dict:
    """Build tool input kwargs from a GuardX ZoneEvent (Phase 6 prep)."""
    return {
        "event_description": zone_event_to_query(event),
        "zone_name": event.zone_name,
        "event_type": event.event_type,
        "camera_id": str(event.camera_id),
    }
