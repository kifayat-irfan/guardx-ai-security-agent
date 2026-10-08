"""SenseNova provider tests — every HTTP interaction is mocked.

Zero real API calls: all SenseNova traffic goes through
``httpx.MockTransport``. The real key is never needed here.
"""
import json
import uuid
from pathlib import Path

import httpx
import pytest

from app.core.config import get_settings
from app.incidents.service import IncidentWorkflowService
from app.langchain import llm as llm_module
from app.langchain.llm import (
    LLMConfig,
    LLMUnavailableError,
    get_llm,
    get_llm_config,
    is_available,
)
from app.langchain.sensenova import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    SenseNovaAPIError,
    SenseNovaChatModel,
)
from app.langchain.service import LangChainService
from app.rag.service import PolicyRAGService
from app.zone_engine.events import ZoneEvent

POLICIES_DIR = Path(__file__).resolve().parent.parent.parent / "policies"

_STUB_KEYS = (
    "restricted", "server", "unauthorized", "person", "enter", "zone",
    "room", "severity", "policy", "intrusion", "access", "alert",
)


def stub_embed(texts):
    return [
        [1.0 if k in t.lower() else 0.0 for k in _STUB_KEYS] + [0.1]
        for t in texts
    ]


def make_lc(tmp_path, collection):
    rag = PolicyRAGService(
        policies_dir=POLICIES_DIR, persist_dir=tmp_path / "chroma",
        collection=collection, model_name="stub", embed_fn=stub_embed,
    )
    rag.reindex()
    return LangChainService(rag_service=rag)


def make_event():
    return ZoneEvent(
        event_id=uuid.uuid4(), camera_id=uuid.uuid4(), zone_id=uuid.uuid4(),
        zone_name="server-room", tracking_id=2, event_type="zone_enter",
        timestamp=1700000000.0, confidence=0.87,
        bounding_box=[0.4, 0.5, 0.6, 0.9], point=[0.5, 0.9], metadata={},
    )


ANALYSIS = {
    "summary": "Person #2 entered the server-room restricted zone.",
    "severity": "HIGH",
    "recommended_action": "Dispatch security to verify authorization.",
    "cited_policy_chunk_ids": [],
    "reasoning": "FACT: a person entered a restricted zone. "
                 "RECOMMENDATION: verify authorization per policy.",
    "confidence": 0.9,
}


def success_body(content=None):
    return {
        "id": "chatcmpl-test",
        "model": DEFAULT_MODEL,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant",
                        "content": json.dumps(content or ANALYSIS)},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }


def mock_client(handler, **model_kwargs):
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    kwargs = {"api_key": "test-key", "http_client": client, "retries": 0}
    kwargs.update(model_kwargs)
    return SenseNovaChatModel(**kwargs)


# -- fixtures ------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_llm_cache():
    llm_module._llm = None
    llm_module._llm_config = None
    yield
    llm_module._llm = None
    llm_module._llm_config = None


@pytest.fixture
def sensenova_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "sensenova")
    monkeypatch.setenv("SENSENOVA_API_KEY", "test-key-env")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# -- configuration -------------------------------------------------------


def test_sensenova_settings_defaults(monkeypatch):
    from app.core.config import Settings

    # Isolate from the developer's real .env (which holds a live API key):
    # defaults must be verifiable without ambient secrets.
    for var in (
        "SENSENOVA_API_KEY",
        "SENSENOVA_BASE_URL",
        "SENSENOVA_MODEL",
        "SENSENOVA_MAX_TOKENS",
        "SENSENOVA_RETRIES",
    ):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.sensenova_api_key == ""
    assert s.sensenova_model == DEFAULT_MODEL
    assert s.sensenova_base_url == DEFAULT_BASE_URL
    assert s.sensenova_max_tokens > 0
    assert s.sensenova_retries >= 0


def test_get_llm_config_sensenova(sensenova_env):
    cfg = get_llm_config()
    assert cfg.provider == "sensenova"
    assert cfg.model == DEFAULT_MODEL
    assert cfg.base_url == DEFAULT_BASE_URL
    assert cfg.api_key == "test-key-env"
    # repr must never carry the key
    assert "test-key-env" not in repr(cfg)


def test_is_available_requires_key():
    assert is_available(LLMConfig(provider="sensenova", api_key="")) is False
    assert is_available(
        LLMConfig(provider="sensenova", api_key="k")) is True


def test_get_llm_raises_without_key():
    cfg = LLMConfig(provider="sensenova", api_key="")
    with pytest.raises(LLMUnavailableError, match="SENSENOVA_API_KEY"):
        get_llm(cfg)


def test_get_llm_rejects_unknown_provider():
    cfg = LLMConfig(provider="not-a-provider")
    with pytest.raises(LLMUnavailableError, match="unknown llm_provider"):
        get_llm(cfg)


def test_get_llm_builds_sensenova_model_with_key():
    cfg = LLMConfig(provider="sensenova", api_key="k")
    model = get_llm(cfg)
    assert isinstance(model, SenseNovaChatModel)
    assert model.model_name == cfg.model
    # second call returns the cached instance (no rebuild)
    assert get_llm(cfg) is model


# -- request construction / response parsing -----------------------------


def test_request_construction():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["payload"] = json.loads(request.content.decode())
        return httpx.Response(200, json=success_body())

    model = mock_client(handler)
    out = model.invoke("hello")
    assert str(out.content)  # parsed content returned
    assert seen["url"] == DEFAULT_BASE_URL + "/chat/completions"
    assert seen["auth"] == "Bearer test-key"  # header, never logged
    payload = seen["payload"]
    assert payload["model"] == DEFAULT_MODEL
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["temperature"] == 0.0
    assert payload["max_tokens"] == 1024
    roles = [m["role"] for m in payload["messages"]]
    assert set(roles) <= {"system", "user", "assistant"}


def test_message_roles_mapped():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content.decode())
        return httpx.Response(200, json=success_body())

    from langchain_core.messages import HumanMessage, SystemMessage

    model = mock_client(handler)
    model.invoke([SystemMessage(content="sys"), HumanMessage(content="hi")])
    roles = [m["role"] for m in seen["payload"]["messages"]]
    assert roles == ["system", "user"]


def test_model_repr_and_params_hide_key():
    model = SenseNovaChatModel(api_key="super-secret-key")
    assert "super-secret-key" not in repr(model)
    assert "super-secret-key" not in json.dumps(model._identifying_params)


# -- error handling ------------------------------------------------------


def test_401_auth_failure_no_retry():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(401, json={
            "error": {"type": "auth_error", "code": 16, "message": "bad key"}})

    model = mock_client(handler, retries=3)
    with pytest.raises(SenseNovaAPIError) as exc_info:
        model.invoke("hello")
    assert exc_info.value.status_code == 401
    assert exc_info.value.retryable is False
    assert len(calls) == 1  # fail fast — no retry storm


def test_429_quota_no_retry():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(429, json={
            "error": {"type": "quota_exceeded_error",
                      "message": "quota exceeded"}})

    model = mock_client(handler, retries=3)
    with pytest.raises(SenseNovaAPIError) as exc_info:
        model.invoke("hello")
    assert exc_info.value.status_code == 429
    assert exc_info.value.retryable is False
    assert len(calls) == 1


def test_500_retries_then_raises():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500, json={
            "error": {"type": "internal_server_error"}})

    model = mock_client(handler, retries=1)
    with pytest.raises(SenseNovaAPIError) as exc_info:
        model.invoke("hello")
    assert exc_info.value.status_code == 500
    assert exc_info.value.retryable is True
    assert len(calls) == 2  # 1 initial + 1 retry, then give up


def test_malformed_envelope_non_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json at all")

    model = mock_client(handler)
    with pytest.raises(SenseNovaAPIError, match="non-JSON"):
        model.invoke("hello")


def test_malformed_envelope_missing_choices():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    model = mock_client(handler)
    with pytest.raises(SenseNovaAPIError, match="missing choices"):
        model.invoke("hello")


def test_timeout_maps_to_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    model = mock_client(handler)
    with pytest.raises(SenseNovaAPIError, match="timed out"):
        model.invoke("hello")


# -- workflow integration (mocked HTTP, real graph) -----------------------


def test_llm_unavailable_path_preserved(tmp_path):
    """Missing key -> factory raises -> decision status llm_unavailable."""
    lc = make_lc(tmp_path, "test_sn_unavail")

    def factory():
        raise LLMUnavailableError("sensenova LLM selected but "
                                  "SENSENOVA_API_KEY is not set")

    svc = IncidentWorkflowService(lc, llm_factory=factory)
    decision = svc.analyze_event(make_event())
    assert decision.status == "llm_unavailable"
    assert decision.severity is None  # never fabricated


def test_graph_e2e_mocked_sensenova(tmp_path):
    """Full LangGraph run against a mocked SenseNova HTTP endpoint."""
    lc = make_lc(tmp_path, "test_sn_e2e")
    event = make_event()
    chunk_ids = [d.metadata["chunk_id"]
                 for d in lc.retrieve_for_event(event, top_k=3)]
    assert chunk_ids, "stub RAG must retrieve policies for the fixture event"

    analysis = dict(ANALYSIS)
    analysis["cited_policy_chunk_ids"] = [chunk_ids[0]]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=success_body(analysis))

    model = mock_client(handler)
    svc = IncidentWorkflowService(lc, llm_factory=lambda: model)
    decision = svc.analyze_event(event)

    assert decision.status == "completed"
    assert decision.severity == "HIGH"
    assert decision.summary.startswith("Person #2 entered")
    assert decision.cited_policy_chunk_ids == [chunk_ids[0]]
    assert decision.confidence == 0.9
    # grounding: cited ids are a subset of what RAG actually retrieved
    assert set(decision.cited_policy_chunk_ids) <= set(chunk_ids)


def test_graph_e2e_mocked_malformed_output(tmp_path):
    """Malformed model JSON -> analysis_failed, never a fake decision."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=success_body("definitely not json"))

    lc = make_lc(tmp_path, "test_sn_malformed")
    model = mock_client(handler)
    svc = IncidentWorkflowService(lc, llm_factory=lambda: model)
    decision = svc.analyze_event(make_event())
    assert decision.status == "analysis_failed"
    assert decision.severity is None
