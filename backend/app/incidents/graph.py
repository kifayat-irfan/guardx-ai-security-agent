"""Incident workflow graph — LangGraph controls the workflow.

Nodes:
    validate_event -> build_policy_query -> retrieve_policies
        -> analyze_event -> validate_analysis -> build_decision -> END

Failure routing: any node that sets a terminal ``status`` routes straight
to ``build_decision``, which emits a structured failure decision. Nothing
silently continues after a critical failure.
"""
from __future__ import annotations

from functools import partial
from typing import Any, Callable

from langgraph.graph import END, StateGraph

from app.incidents import nodes
from app.incidents.state import TERMINAL_STATUSES, IncidentState
from app.langchain.llm import get_llm
from app.langchain.service import LangChainService

NODES = (
    "validate_event",
    "build_policy_query",
    "retrieve_policies",
    "analyze_event",
    "validate_analysis",
    "build_decision",
)

_NEXT = {
    "validate_event": "build_policy_query",
    "build_policy_query": "retrieve_policies",
    "retrieve_policies": "analyze_event",
    "analyze_event": "validate_analysis",
    "validate_analysis": "build_decision",
}


def _route(state: IncidentState, node: str) -> str:
    """Continue on success; finish the decision on any terminal status."""
    if state.get("status") in TERMINAL_STATUSES and state["status"] != "running":
        return "build_decision"
    return _NEXT[node]


def _default_llm_factory() -> Any:
    return get_llm()  # raises LLMUnavailableError when no local LLM


def build_incident_graph(
    lc_service: LangChainService,
    llm_factory: Callable[[], Any] | None = None,
):
    """Build (and compile) the incident workflow graph."""
    ctx = nodes.NodeContext(
        lc_service=lc_service,
        llm_factory=llm_factory or _default_llm_factory,
    )
    graph = StateGraph(IncidentState)
    for name in NODES:
        fn = getattr(nodes, name)
        graph.add_node(name, partial(fn, ctx=ctx))
    graph.set_entry_point("validate_event")
    for node, nxt in _NEXT.items():
        graph.add_conditional_edges(
            node,
            partial(_route, node=node),
            {"build_decision": "build_decision", nxt: nxt},
        )
    graph.add_edge("build_decision", END)
    return graph.compile()


def describe_graph() -> dict:
    """Static graph description for docs/health (no services needed)."""
    return {
        "nodes": list(NODES),
        "edges": [
            {"from": n, "to": _NEXT[n]} for n in _NEXT
        ] + [
            {"from": n, "to": "build_decision", "on": "terminal status"}
            for n in _NEXT
        ],
    }
