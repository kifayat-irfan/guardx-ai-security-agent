"""Incident endpoints — LangGraph analysis + PostgreSQL persistence (Phase 7).

- POST /analyze: run the workflow; persist incident (+ report on success).
- GET /: paginated, filterable incident history.
- GET /{id}: incident + report detail.
- GET /{id}/report: the generated report.
- POST /{id}/reprocess: re-run analysis on the stored event, update in
  place (never duplicates the incident).
- GET /workflows/{id}, GET /status: Phase 6 in-memory workflow inspection.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import get_logger
from app.incidents.repository import IncidentRepository
from app.incidents.schemas import (
    IncidentDecision,
    IncidentDetail,
    IncidentList,
    IncidentOut,
    IncidentReportOut,
)
from app.incidents.service import (
    IncidentWorkflowService,
    get_incident_service,
)
from app.zone_engine.events import ZoneEvent

logger = get_logger(__name__)

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _persist_decision(
    repo: IncidentRepository,
    service: IncidentWorkflowService,
    decision: IncidentDecision,
):
    """Persist the workflow outcome. Returns (incident, report|None).

    Raises HTTPException(500) if persistence itself fails — never claims
    the incident was saved when it wasn't.
    """
    artifacts = service.get_workflow_artifacts(decision.workflow_id) or {}
    try:
        incident, report = repo.persist_workflow_result(
            event=artifacts.get("event") or {},
            decision=decision.model_dump(mode="json"),
            analysis=artifacts.get("analysis"),
            retrieved_chunk_ids=artifacts.get("retrieved_chunk_ids") or [],
        )
    except Exception as exc:  # noqa: BLE001 - persistence failure is a 500
        logger.exception("incident persistence failed")
        raise HTTPException(
            status_code=500, detail=f"incident not saved: {exc}"
        )
    return incident, report


@router.post("/analyze", response_model=IncidentDecision)
def analyze_incident(
    event: ZoneEvent,
    service: IncidentWorkflowService = Depends(get_incident_service),
    db: Session = Depends(get_db),
):
    """Run the LangGraph workflow, persist the incident (+ report on
    success), and return the decision with its persisted ``incident_id``.

    Workflow failures are persisted as failure-status incidents (no
    report) — the structured failure is returned, never a fake success.
    """
    try:
        decision = service.analyze_event(event)
    except Exception as exc:  # noqa: BLE001 - report, don't crash
        raise HTTPException(status_code=500, detail=f"workflow failed: {exc}")
    repo = IncidentRepository(db)
    incident, _ = _persist_decision(repo, service, decision)
    decision.incident_id = str(incident.id)
    return decision


@router.get("", response_model=IncidentList)
def list_incidents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    severity: str | None = Query(None),
    camera_id: str | None = Query(None),
    zone_name: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Incident history, newest first, with optional filters."""
    repo = IncidentRepository(db)
    items, total = repo.list_incidents(
        page=page, page_size=page_size, status=status, severity=severity,
        camera_id=camera_id, zone_name=zone_name,
    )
    total_pages = max(1, (total + page_size - 1) // page_size)
    return IncidentList(
        items=[IncidentOut.model_validate(i) for i in items],
        page=page, page_size=page_size, total=total, total_pages=total_pages,
    )


@router.get("/status")
def incident_status(
    service: IncidentWorkflowService = Depends(get_incident_service),
):
    return service.status()


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


@router.get("/{incident_id}", response_model=IncidentDetail)
def get_incident(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    repo = IncidentRepository(db)
    incident = repo.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    report = repo.get_report(incident_id)
    return IncidentDetail(
        incident=IncidentOut.model_validate(incident),
        report=IncidentReportOut.model_validate(report) if report else None,
    )


@router.get("/{incident_id}/report", response_model=IncidentReportOut)
def get_incident_report(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    repo = IncidentRepository(db)
    report = repo.get_report(incident_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return IncidentReportOut.model_validate(report)


@router.post("/{incident_id}/reprocess", response_model=IncidentDecision)
def reprocess_incident(
    incident_id: uuid.UUID,
    service: IncidentWorkflowService = Depends(get_incident_service),
    db: Session = Depends(get_db),
):
    """Re-run analysis on the stored event (e.g. after a policy change +
    reindex). Updates the incident in place and replaces its report —
    never creates a duplicate incident row.
    """
    repo = IncidentRepository(db)
    incident = repo.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    try:
        decision = service.analyze_event(dict(incident.event_data))
    except Exception as exc:  # noqa: BLE001 - report, don't crash
        raise HTTPException(status_code=500, detail=f"workflow failed: {exc}")
    artifacts = service.get_workflow_artifacts(decision.workflow_id) or {}
    try:
        repo.update_incident_with_decision(
            incident,
            event=artifacts.get("event") or dict(incident.event_data),
            decision=decision.model_dump(mode="json"),
            analysis=artifacts.get("analysis"),
            retrieved_chunk_ids=artifacts.get("retrieved_chunk_ids") or [],
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("incident reprocess persistence failed")
        raise HTTPException(
            status_code=500, detail=f"reprocess not saved: {exc}"
        )
    decision.incident_id = str(incident.id)
    return decision
