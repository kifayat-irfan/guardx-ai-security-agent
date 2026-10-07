"""Policy retrieval tool + citation tests (Phase 5)."""
import hashlib
import uuid
from pathlib import Path

import pytest

from app.langchain.service import LangChainService
from app.langchain.tools import build_policy_tool, zone_event_tool_input
from app.rag.service import PolicyRAGService
from app.zone_engine.events import ZoneEvent, ZoneEventType

POLICIES_DIR = Path(__file__).resolve().parent.parent.parent / "policies"


def stub_embed(texts: list[str]) -> list[list[float]]:
    return [
        [b / 255.0 for b in hashlib.sha256(t.encode()).digest()[:8]]
        for t in texts
    ]


@pytest.fixture()
def lc_service(tmp_path):
    rag = PolicyRAGService(
        policies_dir=POLICIES_DIR,
        persist_dir=tmp_path / "chroma",
        collection="test_lc_tool",
        model_name="stub",
        embed_fn=stub_embed,
    )
    rag.reindex()
    return LangChainService(rag_service=rag)


def _event():
    return ZoneEvent(
        camera_id=uuid.uuid4(), zone_id=uuid.uuid4(), zone_name="server-room",
        tracking_id=2, event_type=ZoneEventType.ZONE_ENTER, timestamp=12.5,
        confidence=0.87, bounding_box=[0.4, 0.5, 0.6, 0.9], point=[0.5, 0.9],
        metadata={"dwell_elapsed": 3.2},
    )


def test_policy_tool_retrieves_chunks(lc_service):
    tool = lc_service.policy_tool()
    assert tool.name == "retrieve_security_policy"
    out = tool.invoke({
        "event_description": "Unauthorized person entered restricted server room.",
        "zone_name": "server-room",
        "event_type": "zone_enter",
        "top_k": 3,
    })
    assert len(out["chunks"]) == 3
    assert out["zone_name"] == "server-room"
    assert len(out["retrieved_chunk_ids"]) == 3
    for chunk in out["chunks"]:
        assert chunk["chunk_id"]
        assert chunk["policy_id"]
        assert "content" in chunk


def test_policy_tool_makes_no_decision(lc_service):
    tool = lc_service.policy_tool()
    out = tool.invoke({
        "event_description": "Unauthorized person entered restricted server room."
    })
    # retrieval output only — no decision fields
    assert set(out.keys()) == {
        "query", "zone_name", "event_type", "camera_id",
        "chunks", "retrieved_chunk_ids",
    }
    assert "severity" not in out
    assert "recommended_action" not in out


def test_zone_event_tool_input():
    kwargs = zone_event_tool_input(_event())
    assert kwargs["zone_name"] == "server-room"
    assert kwargs["event_type"] == "zone_enter"
    assert "server room" in kwargs["event_description"]
    assert kwargs["camera_id"]


def test_citation_validation_pass(lc_service):
    docs = lc_service.retrieve_documents("intrusion", top_k=3)
    ids = lc_service.chunk_ids(docs)
    assert lc_service.validate_citations(docs, ids[:2]) is True
    assert lc_service.validate_citations(docs, []) is True


def test_invalid_citation_rejected(lc_service):
    docs = lc_service.retrieve_documents("intrusion", top_k=3)
    ids = lc_service.chunk_ids(docs)
    assert lc_service.validate_citations(docs, ids + ["fabricated#chunk"]) is False
    assert lc_service.validate_citations(docs, ["never#retrieved"]) is False


def test_metadata_survives_tool_output(lc_service):
    tool = lc_service.policy_tool()
    out = tool.invoke({"event_description": "fire emergency evacuation"})
    for chunk in out["chunks"]:
        assert chunk["chunk_id"] in out["retrieved_chunk_ids"]
