"""LangGraph incident workflow tests — fake LLM, no Ollama (Phase 6)."""
import hashlib
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.incidents import nodes
from app.incidents.fake_llm import FakeAnalysisLLM
from app.incidents.graph import build_incident_graph, describe_graph
from app.incidents.nodes import NodeContext
from app.incidents.schemas import IncidentDecision
from app.incidents.service import IncidentWorkflowService, get_incident_service
from app.langchain.llm import LLMUnavailableError
from app.langchain.service import LangChainService
from app.main import app
from app.rag.service import PolicyRAGService
from app.zone_engine.events import ZoneEvent

POLICIES_DIR = Path(__file__).resolve().parent.parent.parent / "policies"


# Keyword-bag stub embedder: deterministic, semantically ordered retrieval
# (texts sharing query keywords rank higher under cosine distance).
_STUB_KEYS = (
    "restricted", "server", "unauthorized", "person", "enter", "zone",
    "room", "severity", "policy", "intrusion", "access", "alert",
    "camera", "visitor", "tailgating", "dwell",
)


def stub_embed(texts: list[str]) -> list[list[float]]:
    vecs = []
    for t in texts:
        s = t.lower()
        vecs.append([1.0 if k in s else 0.0 for k in _STUB_KEYS] + [0.1])
    return vecs


def make_rag(tmp_path, collection, policies_dir=POLICIES_DIR):
    rag = PolicyRAGService(
        policies_dir=policies_dir,
        persist_dir=tmp_path / "chroma",
        collection=collection,
        model_name="stub",
        embed_fn=stub_embed,
    )
    rag.reindex()
    return rag


def make_service(tmp_path, scenario="valid", collection="test_inc",
                 policies_dir=POLICIES_DIR):
    rag = make_rag(tmp_path, collection, policies_dir)
    lc = LangChainService(rag_service=rag)
    fake = FakeAnalysisLLM(scenario=scenario)
    svc = IncidentWorkflowService(lc, llm_factory=lambda: fake)
    return svc, fake


def make_event(**kw):
    base = dict(
        event_id=uuid.uuid4(),
        camera_id=uuid.uuid4(),
        zone_id=uuid.uuid4(),
        zone_name="server-room",
        tracking_id=2,
        event_type="zone_enter",
        timestamp=1700000000.0,  # deterministic test timestamp
        confidence=0.87,
        bounding_box=[0.4, 0.5, 0.6, 0.9],
        point=[0.5, 0.9],
        metadata={},
    )
    base.update(kw)
    return ZoneEvent(**base)


# -- 1. valid event enters graph ------------------------------------------


def test_valid_event_full_happy_path(tmp_path):
    svc, _ = make_service(tmp_path)
    decision = svc.analyze_event(make_event())
    assert isinstance(decision, IncidentDecision)
    assert decision.status == "completed"
    assert decision.severity == "HIGH"
    assert decision.summary
    assert decision.recommended_action
    assert 0.0 <= decision.confidence <= 1.0
    assert decision.retrieved_policy_count == 3
    assert decision.error is None
    assert decision.duration_ms >= 0


# -- 2. invalid event rejected ----------------------------------------------


def test_invalid_event_rejected(tmp_path):
    svc, _ = make_service(tmp_path)
    bad = make_event().model_dump(mode="json")
    del bad["zone_name"]
    decision = svc.analyze_event(bad)
    assert decision.status == "invalid_event"
    assert decision.error["node"] == "validate_event"
    assert "zone_name" in decision.error["message"]
    assert decision.severity is None


def test_invalid_event_type_rejected(tmp_path):
    svc, _ = make_service(tmp_path)
    bad = make_event().model_dump(mode="json")
    bad["event_type"] = "loitering"
    decision = svc.analyze_event(bad)
    assert decision.status == "invalid_event"


def test_confidence_out_of_range_rejected(tmp_path):
    svc, _ = make_service(tmp_path)
    bad = make_event().model_dump(mode="json")
    bad["confidence"] = 1.5
    decision = svc.analyze_event(bad)
    assert decision.status == "invalid_event"


# -- 3-5. query + retrieval ---------------------------------------------------


def test_event_query_generated_correctly(tmp_path):
    rag = make_rag(tmp_path, "test_inc_q")
    lc = LangChainService(rag_service=rag)
    ctx = NodeContext(lc_service=lc, llm_factory=lambda: FakeAnalysisLLM())
    state = {"event": make_event().model_dump(mode="json")}
    update = nodes.build_policy_query(state, ctx)
    assert "server room" in update["policy_query"]
    assert "entered" in update["policy_query"]
    assert update["current_node"] == "build_policy_query"


def test_policy_retrieval_uses_existing_retriever(tmp_path):
    svc, _ = make_service(tmp_path, collection="test_inc_reuse")
    decision = svc.analyze_event(make_event())
    assert decision.retrieved_policy_count == 3
    wf = svc.get_workflow(decision.workflow_id)
    assert wf is not None
    assert len(wf["retrieved_chunk_ids"]) == 3
    # all chunk IDs use the deterministic Phase 4 scheme
    assert all("#" in cid for cid in wf["retrieved_chunk_ids"])
    # same underlying collection as the RAG service
    assert svc.lc_service.rag_service.collection == "test_inc_reuse"


# -- 6. no-policy path ----------------------------------------------------------


def test_no_policy_path(tmp_path):
    empty = tmp_path / "empty_policies"
    empty.mkdir()
    svc, _ = make_service(tmp_path, collection="test_inc_empty",
                          policies_dir=empty)
    decision = svc.analyze_event(make_event())
    assert decision.status == "no_policies"
    assert decision.retrieved_policy_count == 0
    assert decision.cited_policy_chunk_ids == []
    assert "hallucinate" in decision.error["message"]


# -- 7-10. LLM output validation -----------------------------------------------


def test_invalid_llm_response_malformed(tmp_path):
    svc, _ = make_service(tmp_path, scenario="malformed",
                          collection="test_inc_malformed")
    decision = svc.analyze_event(make_event())
    assert decision.status == "analysis_failed"
    assert decision.error["node"] == "validate_analysis"


def test_invalid_severity_rejected(tmp_path):
    svc, _ = make_service(tmp_path, scenario="bad_severity",
                          collection="test_inc_sev")
    decision = svc.analyze_event(make_event())
    assert decision.status == "analysis_failed"


def test_invalid_confidence_rejected(tmp_path):
    svc, _ = make_service(tmp_path, scenario="bad_confidence",
                          collection="test_inc_conf")
    decision = svc.analyze_event(make_event())
    assert decision.status == "analysis_failed"


# -- 11-12. citation guard -------------------------------------------------------


def test_valid_citations_accepted(tmp_path):
    svc, _ = make_service(tmp_path, collection="test_inc_citok")
    decision = svc.analyze_event(make_event())
    wf = svc.get_workflow(decision.workflow_id)
    retrieved = set(wf["retrieved_chunk_ids"])
    assert set(decision.cited_policy_chunk_ids) <= retrieved
    assert len(decision.cited_policy_chunk_ids) > 0


def test_fabricated_citation_rejected(tmp_path):
    svc, _ = make_service(tmp_path, scenario="fabricated",
                          collection="test_inc_citbad")
    decision = svc.analyze_event(make_event())
    assert decision.status == "citation_invalid"
    assert "fake-policy#rules" in decision.error["message"]


# -- 13. LLM unavailable ----------------------------------------------------------


def test_llm_unavailable_handled(tmp_path):
    rag = make_rag(tmp_path, "test_inc_nollm")

    def _raise():
        raise LLMUnavailableError("no ollama here")

    svc = IncidentWorkflowService(
        LangChainService(rag_service=rag), llm_factory=_raise
    )
    decision = svc.analyze_event(make_event())
    assert decision.status == "llm_unavailable"
    assert decision.error["node"] == "analyze_event"
    assert decision.severity is None  # never faked


# -- 14-15. retrieval / analysis failure -------------------------------------------


def test_retrieval_failure_handled(tmp_path, monkeypatch):
    rag = make_rag(tmp_path, "test_inc_retrfail")
    lc = LangChainService(rag_service=rag)

    def _boom(event, top_k=3):
        raise RuntimeError("chroma exploded")

    monkeypatch.setattr(lc, "retrieve_for_event", _boom)
    svc = IncidentWorkflowService(lc, llm_factory=lambda: FakeAnalysisLLM())
    decision = svc.analyze_event(make_event())
    assert decision.status == "retrieval_failed"
    assert decision.error["node"] == "retrieve_policies"


# -- 16. canonical demo scenario -----------------------------------------------------


def test_canonical_demo_scenario(tmp_path):
    """Deterministic end-to-end scenario for the demo/viva."""
    svc, fake = make_service(tmp_path, collection="test_inc_demo")
    event = make_event(
        zone_name="server-room",
        event_type="zone_enter",
        tracking_id=2,
        confidence=0.87,
        timestamp=1700000000.0,
    )
    decision = svc.analyze_event(event)

    # policy query references unauthorized restricted-area entry
    wf = svc.get_workflow(decision.workflow_id)
    # Restricted Area Policy retrieved
    assert any(cid.startswith("restricted-area#")
               for cid in wf["retrieved_chunk_ids"])
    # valid severity + structure
    assert decision.status == "completed"
    assert decision.severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    # citations only from retrieved chunks
    assert set(decision.cited_policy_chunk_ids) <= set(wf["retrieved_chunk_ids"])
    # workflow observability
    assert wf["timings_ms"]["validate_event"] >= 0
    assert wf["current_node"] == "build_decision"
    assert wf["started_at"] <= wf["finished_at"]


# -- 17-18. failure path + fake determinism --------------------------------------------


def test_full_graph_failure_path_invalid_event(tmp_path):
    svc, _ = make_service(tmp_path, collection="test_inc_failpath")
    bad = make_event().model_dump(mode="json")
    bad["tracking_id"] = None
    decision = svc.analyze_event(bad)
    assert decision.status == "invalid_event"
    wf = svc.get_workflow(decision.workflow_id)
    assert wf["error"]["node"] == "validate_event"
    assert wf["decision"]["status"] == "invalid_event"


def test_fake_llm_deterministic():
    fake = FakeAnalysisLLM(scenario="valid")
    prompt = "[chunk_id: restricted-area#rules]\nSome policy text."
    assert fake.invoke(prompt) == fake.invoke(prompt)


# -- 19. API ----------------------------------------------------------------------------


TEST_DB_URL = (
    get_settings().database_url.rsplit("/", 1)[0] + "/guardx_test"
)


@pytest.fixture()
def api_client(tmp_path):
    # Phase 7+: /analyze persists — keep ALL writes on the test database.
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from app.core.database import Base, get_db

    engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    svc, _ = make_service(tmp_path, collection="test_inc_api")

    def _override_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_incident_service] = lambda: svc
    with TestClient(app) as c:
        yield c, svc
    app.dependency_overrides.clear()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM incident_reports"))
        conn.execute(text("DELETE FROM incidents"))
    engine.dispose()


def test_api_analyze_and_workflow_lookup(api_client):
    client, svc = api_client
    payload = make_event().model_dump(mode="json")
    r = client.post("/api/v1/incidents/analyze", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["severity"] == "HIGH"
    assert body["workflow_id"]

    r = client.get(f"/api/v1/incidents/workflows/{body['workflow_id']}")
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    assert len(r.json()["retrieved_chunk_ids"]) == 3


def test_api_analyze_invalid_event(api_client):
    client, _ = api_client
    payload = make_event().model_dump(mode="json")
    payload["event_type"] = "bogus"
    # ZoneEvent schema itself rejects the bad enum -> 422 at the boundary
    r = client.post("/api/v1/incidents/analyze", json=payload)
    assert r.status_code == 422


def test_api_workflow_not_found(api_client):
    client, _ = api_client
    r = client.get("/api/v1/incidents/workflows/does-not-exist")
    assert r.status_code == 404


def test_api_incident_status(api_client):
    client, _ = api_client
    r = client.get("/api/v1/incidents/status")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] in ("unavailable", "configured", "ready", "error")
    assert "graph" in body


# -- graph structure ----------------------------------------------------------------------


def test_graph_nodes_and_edges():
    desc = describe_graph()
    assert desc["nodes"] == [
        "validate_event", "build_policy_query", "retrieve_policies",
        "analyze_event", "validate_analysis", "build_decision",
    ]
    edge_map = {e["from"]: e["to"] for e in desc["edges"] if "on" not in e}
    assert edge_map["validate_event"] == "build_policy_query"
    assert edge_map["validate_analysis"] == "build_decision"


def test_graph_compiles(tmp_path):
    rag = make_rag(tmp_path, "test_inc_compile")
    lc = LangChainService(rag_service=rag)
    graph = build_incident_graph(lc, llm_factory=lambda: FakeAnalysisLLM())
    assert graph is not None
