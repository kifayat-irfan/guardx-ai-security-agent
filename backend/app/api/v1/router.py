"""API v1 router aggregator — Phase 2+ routers register here."""
from fastapi import APIRouter

from app.api.v1.routers import health

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
# Phase 2: cameras, stream   | Phase 3: zones
# Phase 4: policies          | Phase 6: incidents
# Phase 9: notifications     | Phase 8: events (SSE)
