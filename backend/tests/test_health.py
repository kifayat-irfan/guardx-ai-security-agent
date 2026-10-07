"""Phase 1 gate: health endpoints respond correctly."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_health_returns_ok_and_version():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_v1_health_returns_ok_and_version():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_detailed_health_reports_all_components():
    resp = client.get("/api/v1/health/detailed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    for component in ("postgres", "chromadb", "yolo"):
        assert component in body
        assert body[component]["status"] in ("up", "down")


def test_openapi_includes_v1_routes():
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/health/detailed" in paths
