"""LangChainService — the LangChain integration boundary.

Owns the GuardX policy retriever, the retrieval tool, the analysis prompt,
and optional isolated LLM invocation. Testable without any LLM: every
method except ``invoke_analysis`` works with retrieval alone.

LangChain integrates retrieval + future reasoning. It does NOT replace the
Phase 4 RAG store and does NOT control the workflow (Phase 6/LangGraph).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import StructuredTool

from app.core.logging import get_logger
from app.langchain.documents import retrieved_chunk_to_document
from app.langchain.llm import (
    LLMConfig,
    LLMUnavailableError,
    get_llm,
    get_llm_config,
    is_available,
)
from app.langchain.prompts import build_security_analysis_prompt, format_policy_context
from app.langchain.retriever import GuardXPolicyRetriever
from app.langchain.schemas import SecurityAnalysis
from app.langchain.tools import build_policy_tool
from app.rag.citations import validate_citations
from app.rag.schemas import RetrievedChunk
from app.rag.service import PolicyRAGService
from app.zone_engine.events import ZoneEvent

logger = get_logger(__name__)


@dataclass
class LangChainStatus:
    state: str  # unavailable | configured | ready | error
    detail: str | None = None
    llm_model: str | None = None
    llm_provider: str | None = None
    llm_available: bool = False
    retriever_ready: bool = False
    collection: str | None = None


class LangChainService:
    def __init__(self, rag_service: PolicyRAGService,
                 llm_config: LLMConfig | None = None):
        self.rag_service = rag_service
        self.llm_config = llm_config or get_llm_config()
        self._retriever: GuardXPolicyRetriever | None = None
        self._tool: StructuredTool | None = None
        self._prompt: ChatPromptTemplate | None = None
        # RLock: policy_tool() -> retriever() re-enters the same lock
        self._lock = threading.RLock()

    # -- components ------------------------------------------------------
    def retriever(self, top_k: int = 3) -> GuardXPolicyRetriever:
        with self._lock:
            if self._retriever is None:
                self._retriever = GuardXPolicyRetriever(
                    rag_service=self.rag_service, top_k=top_k
                )
            self._retriever.top_k = top_k
            return self._retriever

    def policy_tool(self) -> StructuredTool:
        with self._lock:
            if self._tool is None:
                self._tool = build_policy_tool(self.retriever())
            return self._tool

    def analysis_prompt(self) -> ChatPromptTemplate:
        with self._lock:
            if self._prompt is None:
                self._prompt = build_security_analysis_prompt()
            return self._prompt

    # -- retrieval ---------------------------------------------------------
    def retrieve_documents(self, query: str, top_k: int = 3) -> list[Document]:
        return self.retriever(top_k=top_k).invoke(query)

    def retrieve_for_event(self, event: ZoneEvent,
                           top_k: int = 3) -> list[Document]:
        from app.langchain.tools import zone_event_tool_input
        from app.rag.event_query import zone_event_to_query

        return self.retrieve_documents(zone_event_to_query(event), top_k=top_k)

    @staticmethod
    def chunk_ids(documents: list[Document]) -> list[str]:
        return [d.metadata.get("chunk_id") for d in documents]

    @staticmethod
    def validate_citations(documents: list[Document],
                           cited_ids: list[str]) -> bool:
        return validate_citations(
            LangChainService.chunk_ids(documents), cited_ids
        )

    # -- prompt rendering (isolated testing, Phase 6 executes) ---------------
    def render_analysis_prompt(self, event: ZoneEvent,
                               documents: list[Document]) -> str:
        prompt = self.analysis_prompt()
        messages = prompt.format_messages(
            event_type=event.event_type,
            zone_name=event.zone_name,
            timestamp=event.timestamp,
            tracking_id=event.tracking_id,
            confidence=event.confidence,
            policy_context=format_policy_context(documents),
        )
        return "\n\n".join(
            f"{m.type.upper()}: {m.content}" for m in messages
        )

    # -- optional isolated LLM invocation ------------------------------------
    def invoke_analysis(self, event: ZoneEvent, top_k: int = 3) -> str:
        """Run the analysis prompt against the local LLM (testing only).

        Raises LLMUnavailableError when no LLM is reachable. Never persists
        anything — Phase 6 owns decisions and persistence.
        """
        llm = get_llm(self.llm_config)  # raises if unavailable
        documents = self.retrieve_for_event(event, top_k=top_k)
        prompt_value = self.analysis_prompt().invoke(
            {
                "event_type": event.event_type,
                "zone_name": event.zone_name,
                "timestamp": event.timestamp,
                "tracking_id": event.tracking_id,
                "confidence": event.confidence,
                "policy_context": format_policy_context(documents),
            }
        )
        return llm.invoke(prompt_value)

    # -- status ----------------------------------------------------------------
    def status(self) -> LangChainStatus:
        llm_ok = is_available(self.llm_config)
        provider = self.llm_config.provider
        try:
            rag_state = self.rag_service.status().state
        except Exception:  # noqa: BLE001 - status must not raise
            rag_state = "error"
        retriever_ready = rag_state == "ready"
        if rag_state == "error":
            state = "error"
            detail = "underlying RAG service is in error"
        elif not retriever_ready:
            state = "unavailable"
            detail = "RAG index not ready — POST /api/v1/policies/reindex"
        elif llm_ok:
            state = "ready"
            detail = (f"{provider} LLM reachable "
                      f"(model={self.llm_config.model})")
        elif provider == "sensenova":
            state = "configured"
            detail = "retriever ready; SENSENOVA_API_KEY not set"
        else:
            state = "configured"
            detail = (
                f"retriever ready; local LLM '{self.llm_config.model}' "
                f"not reachable at {self.llm_config.base_url}"
            )
        return LangChainStatus(
            state=state,
            detail=detail,
            llm_model=self.llm_config.model,
            llm_provider=provider,
            llm_available=llm_ok,
            retriever_ready=retriever_ready,
            collection=self.rag_service.collection,
        )


_service = None
_service_lock = threading.Lock()


def get_langchain_service() -> LangChainService:
    """Process-wide LangChain service singleton (no params: FastAPI-safe)."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                from app.rag.service import get_rag_service

                _service = LangChainService(rag_service=get_rag_service())
    return _service
