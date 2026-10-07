"""Security-analysis prompt template (Phase 6 prep — not wired yet).

The template instructs the future model to ground every claim in the
retrieved policy context, cite chunk IDs, and separate facts from
recommendations. It is rendered by LangChainService for isolated testing;
LangGraph will own its execution in Phase 6.
"""
from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

SECURITY_ANALYSIS_SYSTEM = """You are a security policy analyst for the GuardX facility monitoring system.

Rules:
- Analyze ONLY the supplied security event. Do not invent additional facts.
- Treat the retrieved policy sections as the authoritative context.
- Do NOT invent policy rules. If no retrieved policy covers the event, say so explicitly.
- Distinguish observed FACTS from your RECOMMENDATIONS.
- When you cite a policy, include its exact chunk_id (e.g. restricted-area#severity-guidance).
- Return your analysis in the requested structured format."""

SECURITY_ANALYSIS_HUMAN = """Security event:
- event_type: {event_type}
- zone: {zone_name}
- timestamp: {timestamp}
- tracking_id: {tracking_id}
- detection_confidence: {confidence}

Retrieved policy context:
{policy_context}

Analyze the event against the policy context above."""


def build_security_analysis_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", SECURITY_ANALYSIS_SYSTEM),
            ("human", SECURITY_ANALYSIS_HUMAN),
        ]
    )


def format_policy_context(documents) -> str:
    """Render retrieved LangChain Documents as prompt context."""
    blocks = []
    for d in documents:
        md = d.metadata or {}
        blocks.append(
            f"[chunk_id: {md.get('chunk_id')}] "
            f"({md.get('policy_title')}, section: {md.get('section')})\n"
            f"{d.page_content}"
        )
    return "\n\n---\n\n".join(blocks)
