"""Automation service: GuardX events -> n8n webhook (Phase 9).

Failure isolation rules:
- Disabled/not-configured: no network traffic, silent no-op.
- Enabled: delivery runs in a daemon thread AFTER persistence, so a
  slow/failing webhook can never delay or break the incident path.
- All exceptions are contained inside the worker thread.
"""
from __future__ import annotations

import logging
import threading
from functools import lru_cache

from app.automation.n8n import N8nClient, N8nResult
from app.automation.schemas import N8nIncidentPayload
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class AutomationResult:
    def __init__(self, status: str, detail: str | None = None):
        self.status = status  # sent | failed | disabled | not_configured
        self.detail = detail


class AutomationService:
    def __init__(self, client: N8nClient | None = None):
        settings = get_settings()
        self.enabled = settings.n8n_enabled
        self.client = client or N8nClient(
            webhook_url=settings.n8n_webhook_url,
            secret=settings.n8n_webhook_secret,
            timeout_seconds=settings.n8n_webhook_timeout_seconds,
        )

    # -- payload builders ----------------------------------------------------

    def build_zone_payload(self, event) -> N8nIncidentPayload:
        """ZoneEvent -> payload. No AI fields yet — severity stays None."""
        return N8nIncidentPayload(
            event_id=str(event.event_id),
            event_type="zone_event",
            occurred_at=None,
            camera_id=str(event.camera_id),
            zone_id=str(event.zone_id),
            zone_name=event.zone_name,
            source_event_type=str(event.event_type),
            track_id=event.tracking_id,
            detection_confidence=event.confidence,
            status="detected",
        )

    def build_incident_payload(self, incident, decision,
                               reprocessed: bool = False
                               ) -> N8nIncidentPayload:
        """Incident + validated decision -> payload.

        status/severity are copied verbatim — an llm_unavailable incident
        keeps status='llm_unavailable' and severity=None. Nothing is
        invented here.
        """
        return N8nIncidentPayload(
            event_id=str(incident.id),
            event_type="incident",
            occurred_at=incident.occurred_at,
            camera_id=str(incident.camera_id),
            zone_id=str(incident.zone_id),
            zone_name=incident.zone_name,
            source_event_type=incident.event_type,
            track_id=incident.tracking_id,
            detection_confidence=incident.detection_confidence,
            incident_id=str(incident.id),
            workflow_id=decision.workflow_id,
            status=decision.status,
            severity=decision.severity,
            summary=decision.summary,
            analysis=getattr(decision, "reasoning", None),
            cited_policy_chunk_ids=list(
                decision.cited_policy_chunk_ids or []
            ),
            retrieved_policy_count=decision.retrieved_policy_count,
            reprocessed=reprocessed,
        )

    # -- delivery -------------------------------------------------------------

    def _deliver(self, payload: N8nIncidentPayload) -> AutomationResult:
        if not self.enabled:
            return AutomationResult("disabled")
        result: N8nResult = self.client.send(payload)
        return AutomationResult(result.status, result.detail)

    def _dispatch(self, payload: N8nIncidentPayload) -> threading.Thread | None:
        """Fire-and-forget delivery. Returns the thread (tests may join)."""
        if not self.enabled:
            return None
        t = threading.Thread(
            target=self._deliver, args=(payload,),
            daemon=True, name="guardx-n8n",
        )
        t.start()
        return t

    def notify_zone_event(self, event) -> threading.Thread | None:
        return self._dispatch(self.build_zone_payload(event))

    def notify_incident(self, incident, decision,
                        reprocessed: bool = False) -> threading.Thread | None:
        return self._dispatch(
            self.build_incident_payload(incident, decision, reprocessed)
        )

    def notify_incident_sync(self, incident, decision,
                             reprocessed: bool = False) -> AutomationResult:
        """Synchronous delivery (tests / scripts). Still never raises."""
        try:
            return self._deliver(
                self.build_incident_payload(incident, decision, reprocessed)
            )
        except Exception as exc:  # noqa: BLE001 - absolute isolation
            logger.warning("automation sync delivery error: %s",
                           str(exc)[:120])
            return AutomationResult("failed", detail="error")

    # -- status ----------------------------------------------------------------

    def health_status(self) -> tuple[str, str | None]:
        """(state, detail) for the health endpoint.

        disabled | configured | reachable | unreachable | error
        """
        if not self.enabled:
            return "disabled", "N8N_ENABLED=false"
        if not self.client.configured:
            return "configured", "enabled, webhook URL not set"
        try:
            probe = self.client.check_reachable()
            if probe == "reachable":
                return "reachable", self._safe_url()
            return "unreachable", self._safe_url()
        except Exception as exc:  # noqa: BLE001 - health must not raise
            return "error", str(exc)[:120]

    def public_status(self) -> dict:
        """Safe status for GET /api/v1/automation/status (no secrets)."""
        state, _ = self.health_status()
        return {
            "enabled": self.enabled,
            "configured": self.client.configured,
            "reachable": state == "reachable",
            "provider": "n8n",
        }

    def _safe_url(self) -> str:
        # host only — never the secret, never query strings
        url = self.client.webhook_url
        try:
            from urllib.parse import urlsplit

            parts = urlsplit(url)
            return f"{parts.scheme}://{parts.netloc}{parts.path}"
        except Exception:  # noqa: BLE001
            return "(webhook configured)"


@lru_cache
def get_automation_service() -> AutomationService:
    return AutomationService()
