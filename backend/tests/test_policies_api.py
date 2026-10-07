"""Policies API tests — service overridden with stub embeddings (Phase 4)."""
import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rag.service import PolicyRAGService, get_rag_service

POLICIES_DIR = Path(__file__).resolve().parent.parent.parent / "policies"


def _stub_embed(texts: list[str]) -> list[list[float]]:
    return [
        [b / 255.0 for b in hashlib.sha256(t.encode()).digest()[:8]]
        for t in texts
    ]


@pytest.fixture()
def client(tmp_path):
    svc = PolicyRAGService(
        policies_dir=POLICIES_DIR,
        persist_dir=tmp_path / "chroma",
        collection="test_api_policies",
        model_name="stub",
        embed_fn=_stub_embed,
    )
    app.dependency_overrides[get_rag_service] = lambda: svc
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_reindex_endpoint(client):
    r = client.post("/api/v1/policies/reindex")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["indexed_documents"] == 5
    assert body["indexed_chunks"] == 20
    assert body["collection"] == "test_api_policies"
    assert body["embedding_model"] == "stub"


def test_search_endpoint(client):
    client.post("/api/v1/policies/reindex")
    r = client.post(
        "/api/v1/policies/search",
        json={"query": "unauthorized person in server room", "top_k": 3},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["chunks"]) == 3
    assert body["chunks"][0]["chunk_id"]
    assert 0.0 <= body["chunks"][0]["score"] <= 1.0


def test_search_endpoint_rejects_empty_query(client):
    r = client.post("/api/v1/policies/search", json={"query": "", "top_k": 3})
    assert r.status_code == 422


def test_list_and_get_policy_endpoints(client):
    client.post("/api/v1/policies/reindex")
    r = client.get("/api/v1/policies")
    assert r.status_code == 200
    assert len(r.json()) == 5

    r = client.get("/api/v1/policies/restricted-area")
    assert r.status_code == 200
    assert r.json()["title"] == "Restricted Area Policy"

    assert client.get("/api/v1/policies/nope").status_code == 404


def test_policy_chunks_endpoint(client):
    client.post("/api/v1/policies/reindex")
    r = client.get("/api/v1/policies/restricted-area/chunks")
    assert r.status_code == 200
    assert len(r.json()) == 4
    assert all(c["chunk_id"].startswith("restricted-area#") for c in r.json())


def test_rag_status_endpoint(client):
    r = client.get("/api/v1/policies/status")
    assert r.status_code == 200
    assert r.json()["state"] == "unavailable"
    client.post("/api/v1/policies/reindex")
    r = client.get("/api/v1/policies/status")
    assert r.json()["state"] == "ready"
    assert r.json()["chunk_count"] == 20
