"""Incident workflow endpoints — LangGraph analysis, no persistence (Phase 6).

Phase 7 will add incident persistence and reporting; these endpoints only
run the workflow and inspect in-memory workflow state.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.incidents.schemas import IncidentDecision
from app.incidents.service import (
    IncidentWorkflowService,
    get_incident_service,
)
from app.zone_engine.events import ZoneEvent

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.post("/analyze", response_model=IncidentDecision)
def analyze_incident(
    event: ZoneEvent,
    service: IncidentWorkflowService = Depends(get_incident_service),
):
    """Run the LangGraph incident workflow for a zone event.

    Returns a structured IncidentDecision. Nothing is persisted.
    """
    try:
        return service.analyze_event(event)
    except Exception as exc:  # noqa: BLE001 - report, don't crash
        raise HTTPException(status_code=500, detail=f"workflow failed: {exc}")


@router.get("/workflows/{workflow_id}")
def get_workflow(
    workflow_id: str,
    service: IncidentWorkflowService = Depends(get_incident_service),
):
    """Inspect a finished (in-memory) workflow run: nodes, timings, error."""
    state = service.get_workflow(workflow_id)
    if state is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return state


@router.get("/status")
def incident_status(
    service: IncidentWorkflowService = Depends(get_incident_service),
):
    return service.status()
