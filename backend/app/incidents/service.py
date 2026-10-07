"""IncidentWorkflowService — runs the LangGraph incident workflow.

- ``analyze_event`` executes the compiled graph synchronously and returns
  an ``IncidentDecision``. Nothing is persisted (Phase 7).
- Finished workflow states are kept in a small in-memory registry for
  ``GET /api/v1/incidents/workflows/{id}`` inspection.
- The LLM is injectable (tests use FakeAnalysisLLM); the default factory
  uses the Phase 5 local-LLM abstraction and degrades to ``llm_unavailable``.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from app.core.logging import get_logger
from app.incidents.graph import build_incident_graph, describe_graph
from app.incidents.schemas import IncidentDecision
from app.incidents.state import IncidentState
from app.langchain.llm import is_available as llm_is_available
from app.langchain.service import LangChainService
from app.zone_engine.events import ZoneEvent

logger = get_logger(__name__)

_MAX_REGISTRY = 200


class IncidentWorkflowService:
    def __init__(
        self,
        lc_service: LangChainService,
        llm_factory: Callable[[], Any] | None = None,
    ):
        self.lc_service = lc_service
        self.graph = build_incident_graph(lc_service, llm_factory)
        self._workflows: dict[str, dict] = {}
        self._lock = threading.Lock()

    def analyze_event(self, event: ZoneEvent | dict) -> IncidentDecision:
        workflow_id = str(uuid.uuid4())
        started = datetime.now(timezone.utc).isoformat()
        # Raw dicts flow into the graph unvalidated: the validate_event node
        # owns schema checks (missing fields, bad types, bad confidence).
        event_dict = (
            event.model_dump(mode="json") if isinstance(event, ZoneEvent)
            else dict(event)
        )
        initial: IncidentState = {
            "workflow_id": workflow_id,
            "status": "running",
            "current_node": "validate_event",
            "started_at": started,
            "timings_ms": {},
            "event": event_dict,
            "retrieved_policies": [],
            "retrieved_chunk_ids": [],
            "retrieval_ok": False,
        }
        logger.info("incident workflow %s started (%s %s)",
                    workflow_id, event_dict.get("event_type"),
                    event_dict.get("zone_name"))
        final = self.graph.invoke(initial)
        decision = IncidentDecision(**final["decision"])
        with self._lock:
            self._workflows[workflow_id] = {
                k: v for k, v in final.items()
            }
            while len(self._workflows) > _MAX_REGISTRY:
                self._workflows.pop(next(iter(self._workflows)))
        logger.info("incident workflow %s finished: %s",
                    workflow_id, decision.status)
        return decision

    def get_workflow_artifacts(self, workflow_id: str) -> dict | None:
        """Full artifacts needed for persistence: analysis + retrieved ids."""
        with self._lock:
            state = self._workflows.get(workflow_id)
        if state is None:
            return None
        return {
            "analysis": state.get("analysis"),
            "retrieved_chunk_ids": state.get("retrieved_chunk_ids") or [],
            "retrieved_policies": state.get("retrieved_policies") or [],
            "event": state.get("event") or {},
        }

    def get_workflow(self, workflow_id: str) -> dict | None:
        with self._lock:
            state = self._workflows.get(workflow_id)
        if state is None:
            return None
        return {
            "workflow_id": workflow_id,
            "status": state.get("status"),
            "current_node": state.get("current_node"),
            "started_at": state.get("started_at"),
            "finished_at": state.get("finished_at"),
            "timings_ms": state.get("timings_ms", {}),
            "error": state.get("error"),
            "retrieved_chunk_ids": state.get("retrieved_chunk_ids", []),
            "decision": state.get("decision"),
        }

    def status(self) -> dict:
        try:
            rag_state = self.lc_service.rag_service.status().state
        except Exception:  # noqa: BLE001 - status must not raise
            rag_state = "error"
        retriever_ready = rag_state == "ready"
        llm_ok = llm_is_available(self.lc_service.llm_config)
        if not retriever_ready:
            state, detail = "unavailable", "RAG index not ready"
        elif llm_ok:
            state, detail = "ready", "graph compiled; local LLM reachable"
        else:
            state, detail = "configured", (
                "graph compiled; local LLM not reachable "
                "(workflows will report llm_unavailable)"
            )
        return {
            "state": state,
            "detail": detail,
            "graph": describe_graph(),
            "llm_available": llm_ok,
            "retriever_ready": retriever_ready,
        }


_service = None
_service_lock = threading.Lock()


def get_incident_service() -> IncidentWorkflowService:
    """Process-wide incident workflow singleton (FastAPI-safe: no params)."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                from app.langchain.service import get_langchain_service

                _service = IncidentWorkflowService(
                    lc_service=get_langchain_service()
                )
    return _service
