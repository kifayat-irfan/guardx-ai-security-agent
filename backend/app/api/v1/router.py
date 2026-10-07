"""API v1 router aggregator — Phase 2+ routers register here."""
from fastapi import APIRouter

from app.api.v1.routers import (
    cameras,
    events,
    health,
    incidents,
    policies,
    zones,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(cameras.router)
api_router.include_router(zones.router)
api_router.include_router(policies.router)
api_router.include_router(incidents.router)
api_router.include_router(events.router)
# Phase 7: incident persistence | Phase 8: events (SSE)
# Phase 9: notifications
