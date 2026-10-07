"""LangChain API endpoint tests (Phase 5)."""
import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.langchain.llm import LLMConfig
from app.langchain.service import LangChainService, get_langchain_service
from app.main import app
from app.rag.service import PolicyRAGService

POLICIES_DIR = Path(__file__).resolve().parent.parent.parent / "policies"


def stub_embed(texts: list[str]) -> list[list[float]]:
    return [
        [b / 255.0 for b in hashlib.sha256(t.encode()).digest()[:8]]
        for t in texts
    ]


@pytest.fixture()
def client(tmp_path):
    rag = PolicyRAGService(
        policies_dir=POLICIES_DIR,
        persist_dir=tmp_path / "chroma",
        collection="test_lc_api",
        model_name="stub",
        embed_fn=stub_embed,
    )
    rag.reindex()
    svc = LangChainService(
        rag_service=rag,
        llm_config=LLMConfig(base_url="http://127.0.0.1:1",
                             timeout_seconds=1.0),
    )
    app.dependency_overrides[get_langchain_service] = lambda: svc
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_langchain_search_endpoint(client):
    r = client.post(
        "/api/v1/policies/langchain/search",
        json={"query": "unauthorized person in server room", "top_k": 3},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["collection"] == "test_lc_api"
    assert len(body["documents"]) == 3
    doc = body["documents"][0]
    assert doc["page_content"]
    assert doc["metadata"]["chunk_id"]
    assert "#" in doc["metadata"]["chunk_id"]
    assert doc["metadata"]["policy_id"]


def test_langchain_search_rejects_empty_query(client):
    r = client.post(
        "/api/v1/policies/langchain/search", json={"query": "", "top_k": 3}
    )
    assert r.status_code == 422


def test_langchain_status_endpoint(client):
    r = client.get("/api/v1/policies/langchain/status")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "configured"  # RAG ready, no LLM on this box
    assert body["retriever_ready"] is True
    assert body["llm_available"] is False
    assert body["collection"] == "test_lc_api"


def test_detailed_health_includes_langchain(client):
    r = client.get("/api/v1/health/detailed")
    assert r.status_code == 200
    body = r.json()
    assert "langchain" in body
    assert body["langchain"]["status"] in (
        "unavailable", "configured", "ready", "error",
    )
