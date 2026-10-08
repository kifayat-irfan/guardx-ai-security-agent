"""Policy RAG endpoints — retrieval only, no security decisions (Phase 4).

Phase 5 adds the LangChain path (``/langchain/*``): same GuardX ChromaDB
collection and retrieval service, exposed as LangChain documents.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.langchain.service import LangChainService, get_langchain_service
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


class LangChainDocument(BaseModel):
    page_content: str
    metadata: dict


class LangChainSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=3, ge=1, le=20)


class LangChainSearchResult(BaseModel):
    query: str
    collection: str
    documents: list[LangChainDocument]


class LangChainStatusResponse(BaseModel):
    state: str
    detail: str | None = None
    llm_model: str | None = None
    llm_provider: str | None = None
    llm_available: bool = False
    retriever_ready: bool = False
    collection: str | None = None


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


# -- Phase 5: LangChain integration path ---------------------------------


@router.post("/langchain/search", response_model=LangChainSearchResult)
def langchain_search(
    request: LangChainSearchRequest,
    service: LangChainService = Depends(get_langchain_service),
):
    """GuardX query -> LangChain retriever -> GuardX ChromaDB -> Documents."""
    try:
        docs = service.retrieve_documents(request.query, top_k=request.top_k)
    except Exception as exc:  # noqa: BLE001 - report, don't crash
        raise HTTPException(status_code=500, detail=f"search failed: {exc}")
    return LangChainSearchResult(
        query=request.query,
        collection=service.rag_service.collection,
        documents=[
            LangChainDocument(page_content=d.page_content, metadata=d.metadata)
            for d in docs
        ],
    )


@router.get("/langchain/status", response_model=LangChainStatusResponse)
def langchain_status(
    service: LangChainService = Depends(get_langchain_service),
):
    st = service.status()
    return LangChainStatusResponse(
        state=st.state,
        detail=st.detail,
        llm_model=st.llm_model,
        llm_provider=st.llm_provider,
        llm_available=st.llm_available,
        retriever_ready=st.retriever_ready,
        collection=st.collection,
    )
