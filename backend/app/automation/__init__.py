"""n8n automation integration (Phase 9) — optional, failure-isolated."""
from app.automation.schemas import N8nIncidentPayload  # noqa: F401
from app.automation.service import (  # noqa: F401
    AutomationResult,
    get_automation_service,
)
