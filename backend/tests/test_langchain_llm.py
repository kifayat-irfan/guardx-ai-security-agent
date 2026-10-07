"""Local LLM abstraction tests — no running LLM required (Phase 5)."""
import uuid

import pytest

from app.langchain.llm import (
    LLMConfig,
    LLMUnavailableError,
    get_llm,
    get_llm_config,
    is_available,
)
from app.langchain.service import LangChainService
from app.zone_engine.events import ZoneEvent, ZoneEventType


def test_llm_config_defaults():
    cfg = get_llm_config()
    assert cfg.provider == "ollama"
    assert cfg.model  # configurable, small default
    assert cfg.base_url.startswith("http")
    assert cfg.timeout_seconds > 0


def test_llm_config_custom():
    cfg = LLMConfig(model="tiny", base_url="http://127.0.0.1:1",
                    timeout_seconds=2.0)
    assert cfg.model == "tiny"


def test_is_available_false_without_server():
    cfg = LLMConfig(base_url="http://127.0.0.1:1", timeout_seconds=1.0)
    assert is_available(cfg) is False


def test_get_llm_raises_when_unavailable():
    cfg = LLMConfig(base_url="http://127.0.0.1:1", timeout_seconds=1.0)
    with pytest.raises(LLMUnavailableError):
        get_llm(cfg)


def test_invoke_analysis_raises_without_llm(tmp_path):
    import hashlib
    from pathlib import Path

    from app.rag.service import PolicyRAGService

    def stub_embed(texts):
        return [
            [b / 255.0 for b in hashlib.sha256(t.encode()).digest()[:8]]
            for t in texts
        ]

    policies = Path(__file__).resolve().parent.parent.parent / "policies"
    rag = PolicyRAGService(
        policies_dir=policies, persist_dir=tmp_path / "chroma",
        collection="test_lc_llm", model_name="stub", embed_fn=stub_embed,
    )
    rag.reindex()
    svc = LangChainService(
        rag_service=rag,
        llm_config=LLMConfig(base_url="http://127.0.0.1:1",
                             timeout_seconds=1.0),
    )
    event = ZoneEvent(
        camera_id=uuid.uuid4(), zone_id=uuid.uuid4(), zone_name="server-room",
        tracking_id=2, event_type=ZoneEventType.ZONE_ENTER, timestamp=12.5,
        confidence=0.87, bounding_box=[0.4, 0.5, 0.6, 0.9], point=[0.5, 0.9],
        metadata={},
    )
    with pytest.raises(LLMUnavailableError):
        svc.invoke_analysis(event)


def test_langchain_status_without_llm(tmp_path):
    import hashlib
    from pathlib import Path

    from app.rag.service import PolicyRAGService

    def stub_embed(texts):
        return [
            [b / 255.0 for b in hashlib.sha256(t.encode()).digest()[:8]]
            for t in texts
        ]

    policies = Path(__file__).resolve().parent.parent.parent / "policies"
    rag = PolicyRAGService(
        policies_dir=policies, persist_dir=tmp_path / "chroma",
        collection="test_lc_status", model_name="stub", embed_fn=stub_embed,
    )
    rag.reindex()
    svc = LangChainService(
        rag_service=rag,
        llm_config=LLMConfig(base_url="http://127.0.0.1:1",
                             timeout_seconds=1.0),
    )
    st = svc.status()
    assert st.state == "configured"  # retriever ready, LLM not reachable
    assert st.llm_available is False
    assert st.retriever_ready is True
    assert st.collection == "test_lc_status"
