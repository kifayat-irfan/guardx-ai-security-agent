"""Incident persistence — PostgreSQL repository (Phase 7).

Database logic lives here, separate from the LangGraph nodes. Incident +
report creation is atomic: if the report fails, the incident rolls back
too. Parameterized SQLAlchemy throughout; explicit rollback on failure.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.incident import Incident
from app.models.incident_report import IncidentReport

logger = get_logger(__name__)

MAX_PAGE_SIZE = 100


def _report_title(event_type: str, zone_name: str) -> str:
    label = "Zone Entry" if event_type == "zone_enter" else "Zone Exit"
    return f"{label} — {zone_name}"


class IncidentRepository:
    def __init__(self, db: Session):
        self.db = db

    # -- create -----------------------------------------------------------

    def create_incident(
        self,
        event: dict,
        decision: dict,
        commit: bool = True,
    ) -> Incident:
        """Build an Incident row from the original event + workflow decision.

        Failed workflows are stored too (failure status, no AI fields) so
        failures stay observable — never marked completed.
        """
        incident = Incident(
            external_event_id=str(event.get("event_id", "")),
            camera_id=uuid.UUID(str(event["camera_id"])),
            zone_id=uuid.UUID(str(event["zone_id"])),
            zone_name=event["zone_name"],
            tracking_id=int(event["tracking_id"]),
            event_type=event["event_type"],
            occurred_at=datetime.now(timezone.utc),
            detection_confidence=float(event.get("confidence", 0.0)),
            bounding_box=list(event.get("bounding_box") or []),
            point=list(event.get("point") or []),
            event_data=dict(event),
            status=decision["status"],
            severity=decision.get("severity"),
            summary=decision.get("summary"),
            recommended_action=decision.get("recommended_action"),
            analysis_confidence=decision.get("confidence"),
            error=decision.get("error"),
            workflow_id=decision["workflow_id"],
        )
        self.db.add(incident)
        if commit:
            self.db.commit()
            self.db.refresh(incident)
        return incident

    def create_report(
        self,
        incident_id: uuid.UUID,
        event: dict,
        decision: dict,
        analysis: dict,
        retrieved_chunk_ids: list[str],
        commit: bool = True,
    ) -> IncidentReport:
        """Build the IncidentReport — citations copied verbatim from the
        validated decision. This layer never generates citations."""
        report = IncidentReport(
            incident_id=incident_id,
            report_type="ai_analysis",
            title=_report_title(event["event_type"], event["zone_name"]),
            summary=decision.get("summary"),
            severity=decision.get("severity"),
            recommended_action=decision.get("recommended_action"),
            reasoning=analysis.get("reasoning"),
            cited_policy_chunk_ids=list(
                decision.get("cited_policy_chunk_ids") or []
            ),
            retrieved_policy_count=decision.get("retrieved_policy_count", 0),
            retrieved_chunk_ids=list(retrieved_chunk_ids or []),
        )
        self.db.add(report)
        if commit:
            self.db.commit()
            self.db.refresh(report)
        return report

    def persist_workflow_result(
        self,
        event: dict,
        decision: dict,
        analysis: dict | None,
        retrieved_chunk_ids: list[str],
    ) -> tuple[Incident, IncidentReport | None]:
        """Atomically persist incident (+ report on success).

        Rolls back everything on any failure — never a half-created
        incident. Returns (incident, report|None).
        """
        try:
            incident = self.create_incident(event, decision, commit=False)
            self.db.flush()  # generate incident.id before the report FK
            report = None
            if decision["status"] == "completed" and analysis:
                report = self.create_report(
                    incident.id, event, decision, analysis,
                    retrieved_chunk_ids, commit=False,
                )
            self.db.commit()
            self.db.refresh(incident)
            if report is not None:
                self.db.refresh(report)
            logger.info("persisted incident %s (%s)", incident.id,
                        decision["status"])
            return incident, report
        except Exception:
            self.db.rollback()
            logger.exception("incident persistence failed; rolled back")
            raise

    # -- update (reprocess) -------------------------------------------------

    def update_incident_with_decision(
        self,
        incident: Incident,
        event: dict,
        decision: dict,
        analysis: dict | None,
        retrieved_chunk_ids: list[str],
    ) -> tuple[Incident, IncidentReport | None]:
        """Reprocess: update the incident in place, replace its report.

        Never creates a duplicate incident row. Atomic.
        """
        try:
            incident.status = decision["status"]
            incident.severity = decision.get("severity")
            incident.summary = decision.get("summary")
            incident.recommended_action = decision.get("recommended_action")
            incident.analysis_confidence = decision.get("confidence")
            incident.error = decision.get("error")
            incident.workflow_id = decision["workflow_id"]
            incident.occurred_at = datetime.now(timezone.utc)
            incident.event_data = dict(event)
            # replace the report (one report per incident)
            if incident.report is not None:
                self.db.delete(incident.report)
                self.db.flush()
            report = None
            if decision["status"] == "completed" and analysis:
                report = self.create_report(
                    incident.id, event, decision, analysis,
                    retrieved_chunk_ids, commit=False,
                )
            self.db.commit()
            self.db.refresh(incident)
            if report is not None:
                self.db.refresh(report)
            logger.info("reprocessed incident %s -> %s", incident.id,
                        decision["status"])
            return incident, report
        except Exception:
            self.db.rollback()
            logger.exception("incident reprocess failed; rolled back")
            raise

    # -- read ---------------------------------------------------------------

    def get_incident(self, incident_id: uuid.UUID) -> Incident | None:
        return self.db.get(Incident, incident_id)

    def get_report(self, incident_id: uuid.UUID) -> IncidentReport | None:
        return self.db.execute(
            select(IncidentReport).where(
                IncidentReport.incident_id == incident_id
            )
        ).scalar_one_or_none()

    def list_incidents(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        severity: str | None = None,
        camera_id: str | None = None,
        zone_name: str | None = None,
    ) -> tuple[list[Incident], int]:
        page = max(1, page)
        page_size = min(max(1, page_size), MAX_PAGE_SIZE)
        stmt = select(Incident)
        count_stmt = select(func.count()).select_from(Incident)
        filters = []
        if status:
            filters.append(Incident.status == status)
        if severity:
            filters.append(Incident.severity == severity)
        if camera_id:
            filters.append(Incident.camera_id == uuid.UUID(camera_id))
        if zone_name:
            filters.append(Incident.zone_name == zone_name)
        for f in filters:
            stmt = stmt.where(f)
            count_stmt = count_stmt.where(f)
        total = self.db.execute(count_stmt).scalar() or 0
        items = (
            self.db.execute(
                stmt.order_by(Incident.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        return list(items), total

    def count(self) -> int:
        return self.db.execute(
            select(func.count()).select_from(Incident)
        ).scalar() or 0
