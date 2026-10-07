"""Health endpoints: liveness + dependency status."""
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

    # Phase 4: report the local RAG/ChromaDB subsystem state.
    # A RAG problem never fails the whole backend — it is reported here.
    try:
        from app.rag.service import get_rag_service

        rag = get_rag_service().status()
        chromadb = ComponentStatus(
            status=rag.state,  # unavailable | initializing | ready | error
            detail=(
                f"{rag.chunk_count} chunks indexed"
                if rag.state == "ready"
                else rag.detail
            ),
        )
    except Exception as exc:  # noqa: BLE001 - health check must not raise
        chromadb = ComponentStatus(status="error", detail=str(exc)[:200])

    # Phase 5: LangChain integration state (never fails the backend).
    try:
        from app.langchain.service import get_langchain_service

        lc = get_langchain_service().status()
        langchain = ComponentStatus(
            status=lc.state,  # unavailable | configured | ready | error
            detail=(
                f"model={lc.llm_model} retriever="
                f"{'ready' if lc.retriever_ready else 'not-ready'}"
            ),
        )
    except Exception as exc:  # noqa: BLE001 - health check must not raise
        langchain = ComponentStatus(status="error", detail=str(exc)[:200])

    # Phase 6: LangGraph workflow state (never fails the backend).
    try:
        from app.incidents.service import get_incident_service

        ig = get_incident_service().status()
        langgraph = ComponentStatus(
            status=ig["state"],  # unavailable | configured | ready | error
            detail=ig["detail"],
        )
    except Exception as exc:  # noqa: BLE001 - health check must not raise
        langgraph = ComponentStatus(status="error", detail=str(exc)[:200])

    # Phase 2 will flip this once the YOLO model is loaded.
    yolo = ComponentStatus(status="down", detail="model not loaded (Phase 2)")

    overall = (
        "ok"
        if postgres.status == "up" and chromadb.status == "up"
        else "degraded"
    )
    # Phase 7: incident persistence state (never fails the backend).
    try:
        from sqlalchemy import text as _text

        from app.core.database import SessionLocal
        from app.models.incident import Incident

        db = SessionLocal()
        try:
            count = db.query(Incident).count()
            rev = db.execute(
                _text("SELECT version_num FROM alembic_version")
            ).scalar()
            latest = _latest_migration()
            postgres_incidents = ComponentStatus(
                status="up",
                detail=(f"{count} incidents; alembic {rev}"
                        + (" (current)" if rev == latest else
                           f" (latest {latest})")),
            )
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 - health check must not raise
        postgres_incidents = ComponentStatus(
            status="down", detail=str(exc)[:200]
        )

    # Phase 9: n8n automation state (never fails the backend).
    # disabled | configured | reachable | unreachable | error
    try:
        from app.automation.service import get_automation_service

        n8n_state, n8n_detail = get_automation_service().health_status()
        n8n = ComponentStatus(status=n8n_state, detail=n8n_detail)
    except Exception as exc:  # noqa: BLE001 - health check must not raise
        n8n = ComponentStatus(status="error", detail=str(exc)[:200])

    return DetailedHealth(
        status=overall,
        version=settings.app_version,
        postgres=postgres,
        chromadb=chromadb,
        yolo=yolo,
        langchain=langchain,
        langgraph=langgraph,
        postgres_incidents=postgres_incidents,
        n8n=n8n,
    )


def _latest_migration() -> str:
    """Newest alembic revision id from the versions directory."""
    import re
    from pathlib import Path

    # health.py -> routers -> v1 -> api -> app -> backend
    versions = (
        Path(__file__).resolve().parent.parent.parent.parent.parent
        / "alembic" / "versions"
    )
    revs = []
    for f in versions.glob("*.py"):
        m = re.search(r'^revision:\s*str\s*=\s*"([^"]+)"', f.read_text(),
                      re.MULTILINE)
        if m:
            revs.append(m.group(1))
    return max(revs) if revs else "unknown"
