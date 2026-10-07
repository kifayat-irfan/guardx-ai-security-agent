"""LangChain retriever tests — reuses Phase 4 RAG (Phase 5)."""
import hashlib
from pathlib import Path

import pytest

from app.langchain.documents import (
    document_to_chunk_summary,
    retrieved_chunk_to_document,
)
from app.langchain.retriever import GuardXPolicyRetriever
from app.langchain.service import LangChainService
from app.rag.schemas import PolicySearchRequest
from app.rag.service import PolicyRAGService

POLICIES_DIR = Path(__file__).resolve().parent.parent.parent / "policies"


def stub_embed(texts: list[str]) -> list[list[float]]:
    return [
        [b / 255.0 for b in hashlib.sha256(t.encode()).digest()[:8]]
        for t in texts
    ]


@pytest.fixture()
def rag_service(tmp_path):
    svc = PolicyRAGService(
        policies_dir=POLICIES_DIR,
        persist_dir=tmp_path / "chroma",
        collection="test_lc_policies",
        model_name="stub",
        embed_fn=stub_embed,
    )
    svc.reindex()
    return svc


@pytest.fixture()
def lc_service(rag_service):
    return LangChainService(rag_service=rag_service)


def test_retriever_initialization(lc_service):
    r = lc_service.retriever(top_k=3)
    assert isinstance(r, GuardXPolicyRetriever)
    assert r.top_k == 3


def test_existing_collection_reused(lc_service, rag_service):
    r = lc_service.retriever()
    assert r.collection_name == "test_lc_policies"
    # the retriever talks to the SAME store object — no second collection
    assert r.rag_service._get_store() is rag_service._get_store()


def test_no_duplicate_embedding_model(rag_service, lc_service):
    # the RAG service keeps its injected stub; LangChain never loads another
    assert rag_service._embed_fn is stub_embed
    lc_service.retrieve_documents("intrusion", top_k=2)
    assert rag_service._embed_fn is stub_embed


def test_retrieval_returns_documents_with_metadata(lc_service):
    docs = lc_service.retrieve_documents("unauthorized person in server room", top_k=3)
    assert len(docs) == 3
    for d in docs:
        assert d.page_content
        md = d.metadata
        for key in ("chunk_id", "policy_id", "policy_title", "section",
                    "version", "source", "score"):
            assert key in md, f"missing metadata {key}"
        assert "#" in md["chunk_id"]  # deterministic GuardX chunk id


def test_deterministic_chunk_ids_preserved(lc_service):
    docs = lc_service.retrieve_documents("intrusion", top_k=5)
    ids = {d.metadata["chunk_id"] for d in docs}
    # same deterministic scheme as Phase 4
    assert all("#" in i for i in ids)
    assert lc_service.chunk_ids(docs) == [d.metadata["chunk_id"] for d in docs]


def test_chunk_to_document_roundtrip(rag_service):
    result = rag_service.search(PolicySearchRequest(query="fire", top_k=2))
    for chunk in result.chunks:
        doc = retrieved_chunk_to_document(chunk)
        assert doc.page_content == chunk.content
        assert doc.metadata["chunk_id"] == chunk.chunk_id
        assert doc.metadata["policy_id"] == chunk.policy_id
        assert doc.metadata["score"] == chunk.score
        summary = document_to_chunk_summary(doc)
        assert summary["chunk_id"] == chunk.chunk_id


def test_retriever_top_k(lc_service):
    docs = lc_service.retrieve_documents("intrusion", top_k=1)
    assert len(docs) == 1


def test_retrieve_for_event(lc_service):
    import uuid

    from app.zone_engine.events import ZoneEvent, ZoneEventType

    event = ZoneEvent(
        camera_id=uuid.uuid4(), zone_id=uuid.uuid4(), zone_name="server-room",
        tracking_id=2, event_type=ZoneEventType.ZONE_ENTER, timestamp=12.5,
        confidence=0.87, bounding_box=[0.4, 0.5, 0.6, 0.9], point=[0.5, 0.9],
        metadata={},
    )
    docs = lc_service.retrieve_for_event(event, top_k=3)
    assert len(docs) == 3
    assert all(d.metadata.get("chunk_id") for d in docs)
