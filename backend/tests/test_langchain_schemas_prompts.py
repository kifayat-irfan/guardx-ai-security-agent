"""SecurityAnalysis schema + prompt template tests (Phase 5)."""
import uuid

import pytest

from app.langchain.prompts import build_security_analysis_prompt, format_policy_context
from app.langchain.schemas import SecurityAnalysis
from app.langchain.service import LangChainService
from langchain_core.documents import Document


def test_security_analysis_valid():
    a = SecurityAnalysis(
        summary="Person entered the server room without authorization.",
        severity="high",
        recommended_action="Dispatch security to verify identity.",
        cited_policy_chunk_ids=["restricted-area#severity-guidance"],
        reasoning="Fact: zone_enter at 12.5s. Policy states unauthorized presence is HIGH.",
        confidence=0.8,
    )
    assert a.severity == "high"
    assert a.cited_policy_chunk_ids == ["restricted-area#severity-guidance"]


def test_security_analysis_rejects_bad_severity():
    with pytest.raises(Exception):
        SecurityAnalysis(
            summary="x", severity="extreme", recommended_action="y",
        )


def test_security_analysis_rejects_bad_confidence():
    with pytest.raises(Exception):
        SecurityAnalysis(
            summary="x", severity="low", recommended_action="y", confidence=1.5,
        )


def test_security_analysis_rejects_empty_citation():
    with pytest.raises(Exception):
        SecurityAnalysis(
            summary="x", severity="low", recommended_action="y",
            cited_policy_chunk_ids=["  "],
        )


def test_security_analysis_defaults():
    a = SecurityAnalysis(
        summary="x", severity="medium", recommended_action="y",
    )
    assert a.cited_policy_chunk_ids == []
    assert a.confidence == 0.0


def test_prompt_renders_event_and_context():
    docs = [
        Document(
            page_content="Unauthorized presence is HIGH severity.",
            metadata={
                "chunk_id": "restricted-area#severity-guidance",
                "policy_title": "Restricted Area Policy",
                "section": "Severity Guidance",
            },
        )
    ]
    prompt = build_security_analysis_prompt()
    messages = prompt.format_messages(
        event_type="zone_enter",
        zone_name="server-room",
        timestamp=12.5,
        tracking_id=2,
        confidence=0.87,
        policy_context=format_policy_context(docs),
    )
    assert len(messages) == 2
    human = messages[1].content
    assert "zone_enter" in human
    assert "server-room" in human
    assert "restricted-area#severity-guidance" in human
    assert "Unauthorized presence is HIGH severity." in human
    system = messages[0].content
    assert "Do NOT invent policy rules" in system


def test_format_policy_context_empty():
    assert format_policy_context([]) == ""


def test_render_analysis_prompt_via_service(tmp_path):
    import hashlib
    from pathlib import Path

    from app.rag.service import PolicyRAGService
    from app.zone_engine.events import ZoneEvent, ZoneEventType

    def stub_embed(texts):
        return [
            [b / 255.0 for b in hashlib.sha256(t.encode()).digest()[:8]]
            for t in texts
        ]

    policies = Path(__file__).resolve().parent.parent.parent / "policies"
    rag = PolicyRAGService(
        policies_dir=policies, persist_dir=tmp_path / "chroma",
        collection="test_lc_prompt", model_name="stub", embed_fn=stub_embed,
    )
    rag.reindex()
    svc = LangChainService(rag_service=rag)
    event = ZoneEvent(
        camera_id=uuid.uuid4(), zone_id=uuid.uuid4(), zone_name="server-room",
        tracking_id=2, event_type=ZoneEventType.ZONE_ENTER, timestamp=12.5,
        confidence=0.87, bounding_box=[0.4, 0.5, 0.6, 0.9], point=[0.5, 0.9],
        metadata={},
    )
    docs = svc.retrieve_for_event(event, top_k=2)
    rendered = svc.render_analysis_prompt(event, docs)
    assert "zone_enter" in rendered
    assert "server-room" in rendered
    assert "chunk_id" in rendered
