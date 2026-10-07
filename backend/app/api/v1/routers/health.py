"""Health endpoints: liveness + dependency status."""
import httpx
from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import check_postgres
from app.schemas.health import ComponentStatus, DetailedHealth, HealthStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus, include_in_schema=False)
@router.get("/api/v1/health", response_model=HealthStatus)
def health() -> HealthStatus:
    settings = get_settings()
    return HealthStatus(status="ok", version=settings.app_version)


@router.get("/api/v1/health/detailed", response_model=DetailedHealth)
def health_detailed() -> DetailedHealth:
    settings = get_settings()

    pg = check_postgres()
    postgres = ComponentStatus(
        status="up" if pg["status"] == "up" else "down",
        detail=None if pg["status"] == "up" else pg.get("error"),
    )

    chromadb = ComponentStatus(status="down", detail="not checked")
    try:
        url = f"http://{settings.chroma_host}:{settings.chroma_port}/api/v2/heartbeat"
        # trust_env=False: internal health checks must bypass egress proxies.
        with httpx.Client(trust_env=False, timeout=3.0) as client:
            resp = client.get(url)
        if resp.status_code == 200:
            chromadb = ComponentStatus(status="up")
        else:
            chromadb = ComponentStatus(
                status="down", detail=f"HTTP {resp.status_code}"
            )
    except Exception as exc:  # noqa: BLE001 - health check must not raise
        chromadb = ComponentStatus(status="down", detail=str(exc)[:200])

    # Phase 2 will flip this once the YOLO model is loaded.
    yolo = ComponentStatus(status="down", detail="model not loaded (Phase 2)")

    overall = (
        "ok"
        if postgres.status == "up" and chromadb.status == "up"
        else "degraded"
    )
    return DetailedHealth(
        status=overall,
        version=settings.app_version,
        postgres=postgres,
        chromadb=chromadb,
        yolo=yolo,
    )
