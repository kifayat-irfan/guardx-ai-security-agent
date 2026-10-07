"""PolicyRAGService — the RAG boundary.

Responsibilities: load policies -> chunk -> embed -> index (ChromaDB) ->
retrieve -> structured results. Retrieval only; it never makes security
decisions.

Thread-safe singleton access via ``get_rag_service()``. The embedding
function is injectable for deterministic offline tests.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger
from app.rag.chunker import chunk_policies
from app.rag.embeddings import EmbedFn, get_embedder
from app.rag.loader import PolicyDocument, PolicyLoadError, load_policies
from app.rag.schemas import (
    IndexReport,
    PolicyChunk,
    PolicyMeta,
    PolicySearchRequest,
    PolicySearchResult,
    RagStatus,
    RetrievedChunk,
)
from app.rag.store import PolicyStore

logger = get_logger(__name__)

_service = None
_service_lock = threading.Lock()


class PolicyRAGService:
    def __init__(
        self,
        policies_dir: Path | str,
        persist_dir: Path | str,
        collection: str,
        model_name: str,
        embed_fn: EmbedFn | None = None,
    ):
        self.policies_dir = Path(policies_dir)
        self.persist_dir = Path(persist_dir)
        self.collection = collection
        self.model_name = model_name
        self._embed_fn = embed_fn
        self._store: PolicyStore | None = None
        self._store_error: str | None = None
        self._state = "unavailable"  # unavailable|initializing|ready|error
        self._documents: list[PolicyDocument] = []
        self._last_index_at: str | None = None
        self._lock = threading.Lock()

    # -- lifecycle ------------------------------------------------------
    def _embed(self) -> EmbedFn:
        if self._embed_fn is None:
            with self._lock:
                if self._embed_fn is None:
                    self._state = "initializing"
                    self._embed_fn = get_embedder(self.model_name)
        return self._embed_fn

    def _get_store(self) -> PolicyStore:
        if self._store is None:
            with self._lock:
                if self._store is None:
                    try:
                        self._state = "initializing"
                        self._store = PolicyStore(
                            self.persist_dir, self.collection
                        )
                        self._state = "ready"
                    except Exception as exc:  # noqa: BLE001
                        self._state = "error"
                        self._store_error = str(exc)[:300]
                        raise
        return self._store

    def status(self) -> RagStatus:
        detail = None
        if self._state == "error":
            detail = self._store_error
        elif self._state == "unavailable":
            detail = "index not built yet — POST /api/v1/policies/reindex"
        chunk_count = 0
        if self._state == "ready" and self._store is not None:
            try:
                chunk_count = self._store.count()
            except Exception:  # noqa: BLE001 - status must not raise
                pass
        return RagStatus(
            state=self._state,
            detail=detail,
            collection=self.collection,
            chunk_count=chunk_count,
            embedding_model=self.model_name,
        )

    # -- indexing ---------------------------------------------------------
    def reindex(self) -> IndexReport:
        t0 = time.perf_counter()
        docs = load_policies(self.policies_dir)
        chunks = chunk_policies(docs)
        embeddings = self._embed()([c.content for c in chunks])
        store = self._get_store()
        store.upsert(chunks, embeddings)
        duration_ms = (time.perf_counter() - t0) * 1000.0
        with self._lock:
            self._documents = docs
            self._state = "ready"
            from datetime import datetime, timezone

            self._last_index_at = datetime.now(timezone.utc).isoformat()
        logger.info(
            "RAG reindex: %d docs, %d chunks in %.0f ms",
            len(docs), len(chunks), duration_ms,
        )
        return IndexReport(
            indexed_documents=len(docs),
            indexed_chunks=len(chunks),
            collection=self.collection,
            embedding_model=self.model_name,
            duration_ms=round(duration_ms, 1),
        )

    # -- retrieval ----------------------------------------------------------
    def search(self, request: PolicySearchRequest) -> PolicySearchResult:
        t0 = time.perf_counter()
        store = self._get_store()
        query_vec = self._embed()([request.query])[0]
        where: dict | None = None
        if request.policy_id and request.category:
            where = {"$and": [
                {"policy_id": request.policy_id},
                {"category": request.category},
            ]}
        elif request.policy_id:
            where = {"policy_id": request.policy_id}
        elif request.category:
            where = {"category": request.category}
        hits = store.query(query_vec, top_k=request.top_k, where=where)
        chunks = [
            RetrievedChunk(
                chunk_id=h["chunk_id"],
                policy_id=h["policy_id"],
                policy_title=h["policy_title"],
                section=h["section"],
                content=h["content"],
                score=_to_score(h["distance"]),
                metadata=h["metadata"],
            )
            for h in hits
        ]
        return PolicySearchResult(
            query=request.query,
            top_k=request.top_k,
            chunks=chunks,
            took_ms=round((time.perf_counter() - t0) * 1000.0, 1),
        )

    # -- policy reads ---------------------------------------------------------
    def list_policies(self) -> list[PolicyMeta]:
        docs = self._documents or self._safe_load()
        return [
            PolicyMeta(
                policy_id=d.policy_id,
                title=d.title,
                version=d.version,
                effective_date=d.effective_date,
                category=d.category,
                source=d.source,
            )
            for d in docs
        ]

    def get_policy(self, policy_id: str) -> PolicyDocument | None:
        for d in self._documents or self._safe_load():
            if d.policy_id == policy_id:
                return d
        return None

    def get_chunks(self, policy_id: str) -> list[PolicyChunk]:
        doc = self.get_policy(policy_id)
        return chunk_policies([doc]) if doc else []

    def _safe_load(self) -> list[PolicyDocument]:
        try:
            return load_policies(self.policies_dir)
        except PolicyLoadError:
            return []

    @property
    def last_index_at(self) -> str | None:
        return self._last_index_at


def _to_score(distance: float) -> float:
    """Cosine distance (0..2) -> relevance score 0..1."""
    return round(max(0.0, 1.0 - distance / 2.0), 4)


def get_rag_service() -> PolicyRAGService:
    """Process-wide RAG singleton built from settings."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                s = get_settings()
                from pathlib import Path as _P

                # service.py lives at backend/app/rag/service.py ->
                # three parents up is backend/
                base = _P(__file__).resolve().parent.parent.parent  # backend/
                _service = PolicyRAGService(
                    policies_dir=(base / s.rag_policies_dir).resolve(),
                    persist_dir=(base / s.chroma_persist_dir).resolve(),
                    collection=s.chroma_collection,
                    model_name=s.embedding_model,
                )
    return _service
