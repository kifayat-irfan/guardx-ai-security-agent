"""Automation status (Phase 9). Safe, secret-free."""
from fastapi import APIRouter, Depends

from app.automation.service import (
    AutomationService,
    get_automation_service,
)

router = APIRouter(prefix="/automation", tags=["automation"])


@router.get("/status")
def automation_status(
    automation: AutomationService = Depends(get_automation_service),
) -> dict:
    """n8n integration state. Never exposes the webhook secret."""
    return automation.public_status()
