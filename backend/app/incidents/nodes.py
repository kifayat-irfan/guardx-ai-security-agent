"""LangGraph node functions — pure logic, no graph wiring here.

Each node takes ``(state, ctx)`` and returns a state update dict. Nodes never
raise for domain failures: they set a terminal ``status`` + ``error`` and the
graph routes to ``build_decision``. All state stays JSON-serializable.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from langchain_core.documents import Document

from app.core.logging import get_logger
from app.incidents.state import TERMINAL_STATUSES
from app.langchain.llm import LLMUnavailableError
from app.langchain.prompts import format_policy_context
from app.langchain.schemas import SecurityAnalysis
from app.langchain.service import LangChainService
from app.rag.citations import validate_citations
from app.rag.event_query import zone_event_to_query
from app.zone_engine.events import ZoneEvent, ZoneEventType

logger = get_logger(__name__)

REQUIRED_EVENT_FIELDS = (
    "event_id", "camera_id", "zone_id", "zone_name",
    "event_type", "timestamp", "tracking_id",
)
VALID_EVENT_TYPES = ("zone_enter", "zone_exit")

JSON_INSTRUCTION = (
    "\n\nRespond with a SINGLE JSON object only, with exactly these keys:\n"
    '{"summary": str, "severity": "LOW"|"MEDIUM"|"HIGH"|"CRITICAL", '
    '"recommended_action": str, "cited_policy_chunk_ids": [str], '
    '"reasoning": str, "confidence": 0.0-1.0}. '
    "Cite ONLY chunk_ids shown in the policy context above."
)


@dataclass
class NodeContext:
    lc_service: LangChainService
    llm_factory: Callable[[], Any]  # -> object with .invoke(prompt_value)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timed(state: dict, node: str, t0: float, extra: dict) -> dict:
    timings = dict(state.get("timings_ms") or {})
    timings[node] = round((time.perf_counter() - t0) * 1000.0, 1)
    return {"current_node": node, "timings_ms": timings, **extra}


def _fail(state: dict, node: str, t0: float, code: str, message: str) -> dict:
    logger.warning("incident workflow failed at %s: %s", node, message)
    return _timed(state, node, t0, {
        "status": code,
        "error": {"node": node, "code": code, "message": message[:500]},
        "finished_at": _utcnow(),
    })


def _as_event(event_dict: dict) -> ZoneEvent:
    return ZoneEvent(**event_dict)


# -- nodes ---------------------------------------------------------------


def validate_event(state: dict, ctx: NodeContext) -> dict:
    t0 = time.perf_counter()
    event = state.get("event") or {}
    problems = []
    for field in REQUIRED_EVENT_FIELDS:
        if event.get(field) in (None, ""):
            problems.append(f"missing field: {field}")
    if event.get("event_type") not in VALID_EVENT_TYPES:
        problems.append(f"invalid event_type: {event.get('event_type')!r}")
    conf = event.get("confidence")
    if conf is not None:
        try:
            if not (0.0 <= float(conf) <= 1.0):
                problems.append(f"confidence out of range: {conf}")
        except (TypeError, ValueError):
            problems.append(f"confidence not a number: {conf!r}")
    if problems:
        return _fail(state, "validate_event", t0, "invalid_event",
                      "; ".join(problems))
    return _timed(state, "validate_event", t0, {})


def build_policy_query(state: dict, ctx: NodeContext) -> dict:
    t0 = time.perf_counter()
    try:
        query = zone_event_to_query(_as_event(state["event"]))
    except Exception as exc:  # noqa: BLE001 - malformed event dict
        return _fail(state, "build_policy_query", t0, "invalid_event",
                      f"cannot parse event: {exc}")
    return _timed(state, "build_policy_query", t0, {"policy_query": query})


def retrieve_policies(state: dict, ctx: NodeContext) -> dict:
    t0 = time.perf_counter()
    try:
        docs = ctx.lc_service.retrieve_for_event(
            _as_event(state["event"]), top_k=3
        )
    except Exception as exc:  # noqa: BLE001 - retrieval must not crash graph
        return _fail(state, "retrieve_policies", t0, "retrieval_failed",
                      str(exc))
    policies = [
        {
            "chunk_id": d.metadata.get("chunk_id"),
            "policy_id": d.metadata.get("policy_id"),
            "policy_title": d.metadata.get("policy_title"),
            "section": d.metadata.get("section"),
            "content": d.page_content,
            "score": d.metadata.get("score"),
        }
        for d in docs
    ]
    chunk_ids = [p["chunk_id"] for p in policies if p["chunk_id"]]
    if not policies:
        # explicit no-policy path: never hallucinate a policy
        return _timed(state, "retrieve_policies", t0, {
            "retrieved_policies": [],
            "retrieved_chunk_ids": [],
            "retrieval_ok": False,
            "status": "no_policies",
            "error": {
                "node": "retrieve_policies",
                "code": "no_policies",
                "message": "no relevant policies retrieved; refusing to hallucinate",
            },
            "finished_at": _utcnow(),
        })
    return _timed(state, "retrieve_policies", t0, {
        "retrieved_policies": policies,
        "retrieved_chunk_ids": chunk_ids,
        "retrieval_ok": True,
    })


def analyze_event(state: dict, ctx: NodeContext) -> dict:
    t0 = time.perf_counter()
    try:
        llm = ctx.llm_factory()
    except LLMUnavailableError as exc:
        return _fail(state, "analyze_event", t0, "llm_unavailable", str(exc))
    except Exception as exc:  # noqa: BLE001
        return _fail(state, "analyze_event", t0, "analysis_failed",
                      f"LLM init error: {exc}")
    try:
        event = _as_event(state["event"])
        docs = [
            Document(page_content=p["content"], metadata={
                "chunk_id": p["chunk_id"], "policy_title": p["policy_title"],
                "section": p["section"],
            })
            for p in state["retrieved_policies"]
        ]
        messages = ctx.lc_service.analysis_prompt().format_messages(
            event_type=event.event_type,
            zone_name=event.zone_name,
            timestamp=event.timestamp,
            tracking_id=event.tracking_id,
            confidence=event.confidence,
            policy_context=format_policy_context(docs),
        )
        # append the JSON contract as a final human message
        messages = list(messages) + [_human(JSON_INSTRUCTION)]
        raw = llm.invoke(_prompt_value(messages))
        raw_text = raw.content if hasattr(raw, "content") else str(raw)
    except Exception as exc:  # noqa: BLE001 - model errors are domain failures
        return _fail(state, "analyze_event", t0, "analysis_failed", str(exc))
    return _timed(state, "analyze_event", t0, {"analysis_raw": raw_text})


def validate_analysis(state: dict, ctx: NodeContext) -> dict:
    t0 = time.perf_counter()
    raw = state.get("analysis_raw") or ""
    try:
        payload = json.loads(_extract_json(raw))
        analysis = SecurityAnalysis.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - malformed model output
        return _fail(state, "validate_analysis", t0, "analysis_failed",
                      f"model output failed validation: {exc}")
    # citation guard: cited ⊆ retrieved (Phase 4 helper)
    retrieved = state.get("retrieved_chunk_ids") or []
    if not validate_citations(retrieved, analysis.cited_policy_chunk_ids):
        return _fail(
            state, "validate_analysis", t0, "citation_invalid",
            "model cited chunk IDs that were not retrieved: "
            f"{sorted(set(analysis.cited_policy_chunk_ids) - set(retrieved))}",
        )
    return _timed(state, "validate_analysis", t0,
                  {"analysis": analysis.model_dump(mode="json")})


def build_decision(state: dict, ctx: NodeContext) -> dict:
    t0 = time.perf_counter()
    finished = _utcnow()
    started = state.get("started_at", finished)
    try:
        duration_ms = (
            datetime.fromisoformat(finished) - datetime.fromisoformat(started)
        ).total_seconds() * 1000.0
    except Exception:  # noqa: BLE001
        duration_ms = 0.0

    base = {
        "workflow_id": state["workflow_id"],
        "event_id": str((state.get("event") or {}).get("event_id")),
        "retrieved_policy_count": len(state.get("retrieved_policies") or []),
        "started_at": started,
        "finished_at": finished,
        "duration_ms": round(duration_ms, 1),
    }
    if state.get("status") == "running" and state.get("analysis"):
        a = state["analysis"]
        decision = {
            **base,
            "status": "completed",
            "summary": a["summary"],
            "severity": a["severity"],
            "recommended_action": a["recommended_action"],
            "confidence": a["confidence"],
            "cited_policy_chunk_ids": a["cited_policy_chunk_ids"],
            "error": None,
        }
    else:
        decision = {
            **base,
            "status": state.get("status", "analysis_failed"),
            "summary": None,
            "severity": None,
            "recommended_action": None,
            "confidence": None,
            "cited_policy_chunk_ids": [],
            "error": state.get("error"),
        }
    return _timed(state, "build_decision", t0, {
        "status": decision["status"],
        "decision": decision,
        "finished_at": finished,
    })


# -- helpers ---------------------------------------------------------------


def _extract_json(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in model output")
    return text[start:end + 1]


def _human(content: str):
    from langchain_core.messages import HumanMessage

    return HumanMessage(content=content)


def _prompt_value(messages):
    from langchain_core.prompt_values import ChatPromptValue

    return ChatPromptValue(messages=messages)
