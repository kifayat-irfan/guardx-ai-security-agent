"""Policy RAG endpoints — retrieval only, no security decisions (Phase 4)."""
from fastapi import APIRouter, Depends, HTTPException

from app.rag.loader import PolicyLoadError
from app.rag.schemas import (
    IndexReport,
    PolicyChunk,
    PolicyMeta,
    PolicySearchRequest,
    PolicySearchResult,
    RagStatus,
)
from app.rag.service import PolicyRAGService, get_rag_service

router = APIRouter(prefix="/policies", tags=["policies"])


@router.post("/reindex", response_model=IndexReport)
def reindex_policies(
    service: PolicyRAGService = Depends(get_rag_service),
):
    try:
        return service.reindex()
    except PolicyLoadError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - report, don't crash
        raise HTTPException(status_code=500, detail=f"reindex failed: {exc}")


@router.post("/search", response_model=PolicySearchResult)
def search_policies(
    request: PolicySearchRequest,
    service: PolicyRAGService = Depends(get_rag_service),
):
    try:
        return service.search(request)
    except Exception as exc:  # noqa: BLE001 - report, don't crash
        raise HTTPException(status_code=500, detail=f"search failed: {exc}")


@router.get("", response_model=list[PolicyMeta])
def list_policies(service: PolicyRAGService = Depends(get_rag_service)):
    return service.list_policies()


@router.get("/status", response_model=RagStatus)
def rag_status(service: PolicyRAGService = Depends(get_rag_service)):
    return service.status()


@router.get("/{policy_id}", response_model=PolicyMeta)
def get_policy(
    policy_id: str, service: PolicyRAGService = Depends(get_rag_service)
):
    doc = service.get_policy(policy_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="policy not found")
    return PolicyMeta(
        policy_id=doc.policy_id,
        title=doc.title,
        version=doc.version,
        effective_date=doc.effective_date,
        category=doc.category,
        source=doc.source,
    )


@router.get("/{policy_id}/chunks", response_model=list[PolicyChunk])
def get_policy_chunks(
    policy_id: str, service: PolicyRAGService = Depends(get_rag_service)
):
    chunks = service.get_chunks(policy_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="policy not found")
    return chunks
