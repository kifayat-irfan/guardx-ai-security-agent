# Phase 5 — LangChain Integration

**Status: complete and verified (2026-10-07).**

> **LangChain integrates the retrieval and future AI reasoning components.
> It does not replace the GuardX RAG store and it does not control the
> complete workflow.** LangGraph (Phase 6) will own the autonomous incident
> workflow.

Pipeline position after Phase 5:

```
camera → YOLO → tracker → zone engine → zone event → LangChain
                                                        → policy retrieval
                                                     (STOPS HERE)
```

## 1. Why LangChain

GuardX already had deterministic retrieval (Phase 4). LangChain adds the
standard integration primitives the future AI workflow needs — a retriever
interface, a callable policy tool, prompt templates, and structured output
schemas — without duplicating any retrieval logic.

## 2. Relationship to the existing RAG

- The Phase 4 `PolicyRAGService` remains the **only** retrieval implementation.
- `GuardXPolicyRetriever` is a thin `BaseRetriever` adapter around it.
- Same `guardx_policies` ChromaDB collection, same embedding pipeline
  (verified: the retriever talks to the identical store object; the RAG
  service keeps its injected embedding function — LangChain never loads a
  second model).
- `POST /api/v1/policies/search` (Phase 4) is unchanged; the LangChain path
  is exposed separately at `POST /api/v1/policies/langchain/search`.

## 3. Retriever architecture

`backend/app/langchain/retriever.py` — `GuardXPolicyRetriever(BaseRetriever)`:

- Wraps `PolicyRAGService`; `top_k` / `policy_id` / `category` pass through.
- Returns LangChain `Document`s built by `retrieved_chunk_to_document()`,
  preserving **all** GuardX metadata: `chunk_id`, `policy_id`,
  `policy_title`, `section`, `category`, `version`, `source`, `score`.
- The deterministic `chunk_id` (`<policy_id>#<section-slug>`) survives the
  conversion untouched — the citation anchor for Phase 6.

## 4. Policy retrieval tool

`backend/app/langchain/tools.py` — `retrieve_security_policy`
(`StructuredTool`):

- Input: `event_description`, optional `zone_name` / `event_type` /
  `camera_id`, `top_k`.
- Output: `{query, zone_name, event_type, camera_id, chunks[],
  retrieved_chunk_ids[]}` — retrieval only, **no severity or response
  fields** (asserted by tests).
- `zone_event_tool_input(event)` builds tool kwargs directly from a
  `ZoneEvent` (Phase 6 prep).

## 5. Citation integrity

Reuses Phase 4's `validate_citations()`. `LangChainService.validate_citations
(documents, cited_ids)` proves `cited ⊆ retrieved`. Tests cover: valid
citations pass, fabricated chunk IDs fail, metadata survives the
GuardX → Document → tool-output round trip.

## 6. Local LLM abstraction

`backend/app/langchain/llm.py`:

- Ollama via `langchain-ollama`, **optional by design**: `is_available()`
  probes the server; `get_llm()` raises `LLMUnavailableError` with a clear
  message instead of hanging.
- Configurable via env: `llm_provider`, `llm_model` (default
  `llama3.2:1b` — small, CPU-friendly), `llm_base_url`, `llm_timeout_seconds`.
- No API key, no cloud dependency. No test requires a running LLM.
- This box has no Ollama server, so the smoke test verifies graceful
  degradation: status `configured` (retriever ready, LLM unreachable),
  `invoke_analysis` raises `LLMUnavailableError`.
- VM quirk handled: bracketed IPv6 tokens in `no_proxy` break httpx at
  `ollama`-package import time — sanitized in-process before the lazy import.

## 7. Structured analysis schema

`backend/app/langchain/schemas.py` — `SecurityAnalysis` (Phase 6 prep):

```
summary, severity (low|medium|high|critical), recommended_action,
cited_policy_chunk_ids, reasoning, confidence (0-1)
```

Validated with Pydantic; non-empty citation IDs enforced. The LangChain
layer never constructs a final incident from it.

## 8. Security analysis prompt

`backend/app/langchain/prompts.py` — `ChatPromptTemplate` accepting
`event_type`, `zone_name`, `timestamp`, `tracking_id`, `confidence`,
`policy_context`. Instructs the future model to: analyze only the supplied
event, treat retrieved policies as authoritative, never invent rules, cite
exact `chunk_id`s, and separate facts from recommendations. Rendered for
isolated testing via `LangChainService.render_analysis_prompt()`; **not**
wired into any workflow yet.

## 9. API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/policies/langchain/search` | `{query, top_k}` → LangChain `Document`s (page_content + full metadata) over the existing collection |
| GET | `/api/v1/policies/langchain/status` | LangChain state: `unavailable` \| `configured` \| `ready` \| `error`, plus model, retriever, collection |

## 10. Health

`GET /api/v1/health/detailed` now includes a `langchain` component:
`unavailable` (RAG not indexed), `configured` (retriever ready, no LLM),
`ready` (retriever + LLM reachable), `error`. Backend startup never fails
because the LLM is missing.

## 11. Dashboard

Policy panel gains a LangChain row: integration state, retriever status,
and configured LLM model / availability. No chat interface (out of scope).

## 12. Tests (32 new)

- `test_langchain_retriever.py` (8): init, collection reuse (same store
  object), no duplicate embedding model, document metadata, deterministic
  chunk IDs, round-trip conversion, top-k, event retrieval.
- `test_langchain_tools.py` (6): tool retrieval, no-decision output shape,
  event→tool input, citation pass/fail, metadata survival.
- `test_langchain_schemas_prompts.py` (8): schema validation (bad severity /
  confidence / empty citation), prompt rendering with chunk IDs.
- `test_langchain_llm.py` (6): config defaults/custom, unavailable probe,
  `get_llm` / `invoke_analysis` raise cleanly, `configured` status.
- `test_langchain_api.py` (4): search endpoint documents, 422 on empty
  query, status endpoint, health includes langchain.
- Plus a real deadlock caught and fixed during development
  (`RLock` in `LangChainService`).

## 13. Measured resource usage

No additional embedding model loaded (verified). No LLM loaded (none
available on this box). Added packages: `langchain-core 1.6.7`,
`langchain-ollama 1.x` (+ `ollama` client) — pure Python, negligible RAM.

## 14. Known limitations

- `invoke_analysis` is isolated-testing only; no model is configured in
  production yet and none is downloaded.
- The tool mutates `retriever.top_k` per call (documented; fine for the
  single-threaded test path — Phase 6 should pass top_k per invocation).
- Prompt is English-only; policies are English-only.
- No LangGraph, no incident persistence, no notifications — Phase 6+.

## 15. Module map

```
backend/app/langchain/
  service.py     LangChainService: retriever/tool/prompt/LLM orchestration
  retriever.py   GuardXPolicyRetriever(BaseRetriever) over Phase 4 RAG
  tools.py       retrieve_security_policy StructuredTool
  documents.py   RetrievedChunk <-> Document conversion (metadata-preserving)
  prompts.py     security-analysis ChatPromptTemplate
  schemas.py     SecurityAnalysis (Phase 6 prep)
  llm.py         optional Ollama abstraction + graceful degradation
```
