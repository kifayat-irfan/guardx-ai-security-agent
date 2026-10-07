"""LangChain retriever over the existing GuardX RAG store.

GuardXPolicyRetriever is a thin LangChain adapter: it reuses the Phase 4
``guardx_policies`` ChromaDB collection and the existing embedding pipeline.
No second collection, no second embedding model — LangChain is the
integration layer, not a replacement.
"""
from __future__ import annotations

from typing import Any

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, Field

from app.langchain.documents import retrieved_chunk_to_document
from app.rag.schemas import PolicySearchRequest
from app.rag.service import PolicyRAGService


class GuardXPolicyRetriever(BaseRetriever):
    """BaseRetriever adapter around PolicyRAGService."""

    rag_service: PolicyRAGService = Field(exclude=True)
    top_k: int = 3
    policy_id: str | None = None
    category: str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        result = self.rag_service.search(
            PolicySearchRequest(
                query=query,
                top_k=self.top_k,
                policy_id=self.policy_id,
                category=self.category,
            )
        )
        return [retrieved_chunk_to_document(c) for c in result.chunks]

    @property
    def collection_name(self) -> str:
        return self.rag_service.collection

    def as_tool_kwargs(self) -> dict[str, Any]:
        return {"top_k": self.top_k}
