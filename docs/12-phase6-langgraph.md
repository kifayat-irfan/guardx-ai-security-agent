# Phase 6 — LangGraph Autonomous Incident Workflow

**Status: complete and verified (2026-10-07).**

> **LangGraph controls the stateful incident workflow. LangChain provides
> the retrieval and LLM integration. RAG provides the security policy
> context.** No incident persistence, reports, or notifications — Phase 7+.

## 1. Architecture

```
camera → YOLO → tracker → zone engine → zone event
                                              ↓
                                    ┌─────────────────┐
                                    │    LangGraph    │
                                    │  (this phase)   │
                                    │                 │
                                    │ validate_event  │
                                    │       ↓         │
                                    │ build_policy_query
                                    │       ↓         │
                                    │ retrieve_policies ──→ LangChain retriever
                                    │       ↓                    ↓
                                    │ analyze_event ──→ local LLM (Ollama)
                                    │       ↓                    (Phase 5 abstraction)
                                    │ validate_analysis ──→ citation guard
                                    │       ↓              (Phase 4 helper)
                                    │ build_decision      │
                                    └─────────────────┘   │
                                              ↓           │
                                    IncidentDecision      │
                                              ↓           │
                                            STOP (Phase 7 persists)
```

LangGraph owns state and control flow. It never touches ChromaDB or
embeddings directly — retrieval goes through `LangChainService`
(`GuardXPolicyRetriever` over the existing `guardx_policies` collection);
analysis goes through the Phase 5 LLM abstraction.

## 2. IncidentState

`backend/app/incidents/state.py` — a `TypedDict`, **JSON-serializable only**:

| Section | Fields |
|---|---|
| Event | `event` (ZoneEvent as JSON dict) |
| Retrieval | `policy_query`, `retrieved_policies[]` (plain dicts), `retrieved_chunk_ids[]`, `retrieval_ok` |
| Analysis | `analysis_raw`, `analysis` (SecurityAnalysis as JSON dict) |
| Workflow | `workflow_id`, `status`, `current_node`, `error {node, code, message}`, `timings_ms {node: ms}`, `started_at`, `finished_at` |
| Decision | `decision` (IncidentDecision as JSON dict) |

Terminal statuses: `completed`, `invalid_event`, `retrieval_failed`,
`no_policies`, `llm_unavailable`, `analysis_failed`, `citation_invalid`.

## 3. Nodes and edges

| Node | Responsibility |
|---|---|
| `validate_event` | required fields, `event_type ∈ {zone_enter, zone_exit}`, confidence 0–1 |
| `build_policy_query` | `zone_event_to_query()` — natural-language retrieval query, no decisions |
| `retrieve_policies` | `LangChainService.retrieve_for_event()`; empty result → explicit `no_policies` |
| `analyze_event` | renders Phase 5 prompt + JSON contract, invokes local LLM |
| `validate_analysis` | JSON extraction → `SecurityAnalysis` validation → citation guard |
| `build_decision` | assembles the final `IncidentDecision` (success or structured failure) |

Edges are conditional: on success the state flows to the next node; **any
terminal status routes straight to `build_decision`**, which emits the
failure decision. Nothing silently continues after a critical failure.

## 4. Failure paths

| Failure | Status | Behavior |
|---|---|---|
| missing/invalid event fields | `invalid_event` | stops; error names the field |
| retrieval exception | `retrieval_failed` | stops; graph never crashes |
| zero policies retrieved | `no_policies` | stops; **never hallucinates a policy** |
| no local LLM | `llm_unavailable` | stops; never fakes an analysis |
| malformed/invalid model output | `analysis_failed` | stops; no silent repair |
| fabricated citation | `citation_invalid` | stops; no decision emitted |

## 5. Citation guard (critical)

`validate_analysis` reuses the Phase 4 `validate_citations()` helper to
prove `cited_policy_chunk_ids ⊆ retrieved_chunk_ids`. A model citing
`fake-policy#rules` (not retrieved) fails the workflow; citing only
retrieved chunks passes. Verified by dedicated tests both ways.

## 6. Severity enum

Controlled vocabulary only: `LOW | MEDIUM | HIGH | CRITICAL` (Phase 6
guidance: LOW = minor/non-threatening; MEDIUM = unauthorized/suspicious
needing attention; HIGH = confirmed restricted-area violation; LOW…;
CRITICAL = emergency/safety-critical). Arbitrary strings are rejected by
`SecurityAnalysis` validation. These are project policy guidance, not
universal real-world security standards.

## 7. LLM behavior

- Default factory: Phase 5 `get_llm()` (Ollama, configurable model —
  default `llama3.2:1b`). `LLMUnavailableError` → `llm_unavailable` status.
- The prompt enforces: event facts only, retrieved policies authoritative,
  no invented rules/citations, facts separated from recommendations,
  structured JSON output, exact `chunk_id` citations.
- This box has no Ollama server: all tests use a deterministic
  `FakeAnalysisLLM` (scenarios: valid / fabricated / malformed /
  bad_severity / bad_confidence). The suite never requires a real LLM.
- Optional real-LLM smoke test: not run (no server available); the
  `configured` health state documents this.

## 8. API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/incidents/analyze` | run the workflow for a zone event → `IncidentDecision` (nothing persisted) |
| GET | `/api/v1/incidents/workflows/{id}` | inspect a finished run: node timings, chunk IDs, error |
| GET | `/api/v1/incidents/status` | graph description, LLM/retriever availability |

## 9. Observability

`IncidentDecision` carries `workflow_id`, per-node `timings_ms` (via the
workflow lookup), `retrieved_policy_count`, and structured `error`. The
dashboard panel shows the node trace, cited vs retrieved chunk IDs,
severity, confidence, and failures — including an explicit
"AI analysis unavailable" banner when the LLM is down.

## 10. Tests (23 new)

Cover: valid event happy path · invalid event/type/confidence rejected ·
query generation · retriever reuse (same collection) · retrieved IDs in
state · no-policy path · malformed severity/confidence rejected ·
valid/fabricated citations · LLM unavailable · retrieval failure ·
canonical demo scenario · failure path · fake-LLM determinism · API
analyze/workflow-lookup/status/not-found · graph structure · compilation.
Full suite: **154/154** (131 Phase 1–5 + 23 Phase 6).

## 11. Demo scenario

`test_canonical_demo_scenario`: `zone_enter`, zone `server-room`,
`tracking_id=2`, confidence 0.87, deterministic timestamp. Asserts the
Restricted Area Policy is retrieved, severity is valid, citations ⊆
retrieved, status `completed`, and node timings are recorded.

## 12. Module map

```
backend/app/incidents/
  graph.py     StateGraph wiring + conditional failure routing
  nodes.py     six node functions (pure, state-update dicts)
  state.py     IncidentState (serializable)
  schemas.py   IncidentDecision / WorkflowSummary
  service.py   IncidentWorkflowService + in-memory registry + singleton
  fake_llm.py  deterministic FakeAnalysisLLM for tests
```

## 13. Known limitations

- In-memory workflow registry only (bounded at 200, lost on restart) —
  Phase 7 will persist incidents.
- Single LLM call per workflow; no retries, no multi-step reasoning.
- The fake LLM parses chunk IDs from the prompt — test-only; the real path
  uses Ollama JSON output parsed the same way.
- Prompt and policies are English-only.
- Severity guidance is project policy, not a security standard.
