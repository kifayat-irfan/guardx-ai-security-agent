"""RAG service tests — stub embeddings, temp ChromaDB (offline, Phase 4)."""
import hashlib
import shutil
from pathlib import Path

import pytest

from app.rag.chunker import chunk_policies
from app.rag.loader import load_policies
from app.rag.schemas import PolicySearchRequest
from app.rag.service import PolicyRAGService

POLICIES_DIR = Path(__file__).resolve().parent.parent.parent / "policies"
MODEL = "test-stub-model"


def stub_embed(texts: list[str]) -> list[list[float]]:
    """Deterministic 8-dim vectors from text hash — no downloads."""
    vecs = []
    for t in texts:
        h = hashlib.sha256(t.encode()).digest()
        vecs.append([b / 255.0 for b in h[:8]])
    return vecs


@pytest.fixture()
def service(tmp_path):
    persist = tmp_path / "chroma"
    return PolicyRAGService(
        policies_dir=POLICIES_DIR,
        persist_dir=persist,
        collection="test_guardx_policies",
        model_name=MODEL,
        embed_fn=stub_embed,
    )


def test_reindex_counts(service):
    report = service.reindex()
    assert report.indexed_documents == 5
    assert report.indexed_chunks == 20
    assert report.collection == "test_guardx_policies"
    assert report.embedding_model == MODEL
    assert report.duration_ms >= 0
    assert service.status().state == "ready"
    assert service.status().chunk_count == 20


def test_reindex_is_idempotent_no_duplicates(service):
    service.reindex()
    service.reindex()
    service.reindex()
    assert service.status().chunk_count == 20
    ids = service._get_store().get_chunk_ids()
    assert len(ids) == 20  # deterministic IDs -> upsert, never duplicates


def test_search_returns_top_k(service):
    service.reindex()
    result = service.search(PolicySearchRequest(
        query="person entered restricted server room", top_k=3
    ))
    assert len(result.chunks) == 3
    for chunk in result.chunks:
        assert chunk.chunk_id
        assert chunk.policy_id
        assert chunk.policy_title
        assert chunk.section
        assert chunk.content
        assert 0.0 <= chunk.score <= 1.0
        assert chunk.metadata["chunk_id"] == chunk.chunk_id
    # scores sorted best-first
    scores = [c.score for c in result.chunks]
    assert scores == sorted(scores, reverse=True)


def test_search_top_k_behavior(service):
    service.reindex()
    r1 = service.search(PolicySearchRequest(query="intrusion", top_k=1))
    r5 = service.search(PolicySearchRequest(query="intrusion", top_k=5))
    assert len(r1.chunks) == 1
    assert len(r5.chunks) == 5
    assert r1.chunks[0].chunk_id == r5.chunks[0].chunk_id


def test_search_metadata_filter(service):
    service.reindex()
    result = service.search(PolicySearchRequest(
        query="intrusion", top_k=5, category="emergency"
    ))
    assert result.chunks
    assert all(c.metadata["category"] == "emergency" for c in result.chunks)


def test_list_and_get_policy(service):
    service.reindex()
    metas = service.list_policies()
    assert len(metas) == 5
    assert {m.policy_id for m in metas} == {
        "restricted-area", "after-hours-access", "visitor-authorization",
        "emergency-response", "incident-reporting",
    }
    doc = service.get_policy("restricted-area")
    assert doc is not None and doc.title == "Restricted Area Policy"
    assert service.get_policy("nope") is None
    assert len(service.get_chunks("restricted-area")) == 4


def test_policy_edit_reindex_updated_retrieval(tmp_path):
    """Edit a policy -> reindex -> search returns the updated content."""
    workdir = tmp_path / "policies"
    shutil.copytree(POLICIES_DIR, workdir)
    svc = PolicyRAGService(
        policies_dir=workdir,
        persist_dir=tmp_path / "chroma",
        collection="test_edit_flow",
        model_name=MODEL,
        embed_fn=stub_embed,
    )
    svc.reindex()

    # modify the restricted-area rules section
    target = workdir / "restricted-area-policy.md"
    text = target.read_text()
    marker = "UNIQUE-EDIT-MARKER-12345: escorted drones patrol hourly"
    assert marker not in text
    text = text.replace(
        "## Rules",
        "## Rules\n\n" + marker + ".",
        1,
    )
    target.write_text(text)

    report = svc.reindex()
    assert report.indexed_chunks == 20  # same chunk IDs, content updated

    # the rules chunk keeps its deterministic ID but carries new content
    rules_chunks = [
        c for c in svc.get_chunks("restricted-area")
        if c.chunk_id == "restricted-area#rules"
    ]
    assert len(rules_chunks) == 1
    assert marker in rules_chunks[0].content, (
        "updated policy content not present after reindex"
    )

    # and the stored ChromaDB document was updated too
    stored_ids = svc._get_store().get_chunk_ids()
    assert "restricted-area#rules" in stored_ids
    assert len(stored_ids) == 20


def test_status_before_index(tmp_path):
    svc = PolicyRAGService(
        policies_dir=POLICIES_DIR,
        persist_dir=tmp_path / "chroma",
        collection="test_empty",
        model_name=MODEL,
        embed_fn=stub_embed,
    )
    st = svc.status()
    assert st.state == "unavailable"


def test_search_request_validation():
    with pytest.raises(Exception):
        PolicySearchRequest(query="", top_k=3)
    with pytest.raises(Exception):
        PolicySearchRequest(query="x", top_k=0)
    with pytest.raises(Exception):
        PolicySearchRequest(query="x", top_k=21)
