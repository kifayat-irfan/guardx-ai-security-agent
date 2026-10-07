"""LangChain integration layer (Phase 5).

Connects GuardX events to the Phase 4 RAG store through LangChain
primitives (retriever, tool, prompt). Retrieval only — no workflow, no
decisions, no persistence. LangGraph (Phase 6) owns the workflow.
"""
from app.langchain.documents import (  # noqa: F401
    document_to_chunk_summary,
    retrieved_chunk_to_document,
)
from app.langchain.llm import (  # noqa: F401
    LLMConfig,
    LLMUnavailableError,
    get_llm,
    get_llm_config,
    is_available,
)
from app.langchain.prompts import (  # noqa: F401
    build_security_analysis_prompt,
    format_policy_context,
)
from app.langchain.retriever import GuardXPolicyRetriever  # noqa: F401
from app.langchain.schemas import SecurityAnalysis, Severity  # noqa: F401
from app.langchain.service import (  # noqa: F401
    LangChainService,
    LangChainStatus,
    get_langchain_service,
)
from app.langchain.tools import (  # noqa: F401
    PolicyToolInput,
    build_policy_tool,
    zone_event_tool_input,
)
