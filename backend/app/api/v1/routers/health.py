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
        langchain=langchain,
    )
