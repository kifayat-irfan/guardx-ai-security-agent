"""Convert a zone event into a policy-retrieval query (Phase 5/6 prep).

This builds a *retrieval query* — plain descriptive text. It does NOT decide
severity, response, or anything else. LangGraph will consume the retrieved
policies later.
"""
from __future__ import annotations

from app.zone_engine.events import ZoneEvent


def zone_event_to_query(event: ZoneEvent) -> str:
    """Render a ZoneEvent as a natural-language retrieval query."""
    action = (
        "entered the restricted zone"
        if event.event_type == "zone_enter"
        else "exited the restricted zone"
    )
    zone = event.zone_name.replace("-", " ").replace("_", " ")
    parts = [f"Unauthorized person {action} '{zone}'."]
    dwell = (event.metadata or {}).get("dwell_elapsed")
    if dwell:
        parts.append(f"Person remained inside for {dwell} seconds.")
    parts.append(
        "Which security policies apply, what severity guidance holds, "
        "and what is the recommended response?"
    )
    return " ".join(parts)


def describe_event(event: ZoneEvent) -> dict:
    """Structured event summary for future LangGraph consumption."""
    return {
        "camera_id": str(event.camera_id),
        "zone_id": str(event.zone_id),
        "zone_name": event.zone_name,
        "event_type": event.event_type,
        "tracking_id": event.tracking_id,
        "timestamp": event.timestamp,
        "confidence": event.confidence,
    }
