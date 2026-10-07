# Phase 4 — Security Policy RAG

**Status: complete and verified (2026-10-07).**

> **RAG retrieves relevant security policy information. It does not make the
> final security decision.** LangGraph (Phase 6) will consume the retrieved
> policies and run the incident workflow.

Pipeline position after Phase 4:

```
camera → YOLO → tracker → zone engine → zone event → RAG policy retrieval
                                                              (STOPS HERE)
```

## 1. Policy structure

Five project-authored sample policies in `policies/` (Markdown + YAML
front-matter). Each has `policy_id`, `title`, `version`, `effective_date`,
`category`, and four sections:

| File | policy_id | Sections |
|---|---|---|
| `restricted-area-policy.md` | `restricted-area` | Purpose, Rules, Severity Guidance, Recommended Response |
| `after-hours-access-policy.md` | `after-hours-access` | same |
| `visitor-authorization-policy.md` | `visitor-authorization` | same |
| `emergency-response-policy.md` | `emergency-response` | same |
| `incident-reporting-policy.md` | `incident-reporting` | same |

## 2. Chunking strategy

`backend/app/rag/chunker.py` — **one chunk per policy section** (5 policies ×
4 sections = **20 chunks**). Sections longer than 2000 chars split on
paragraph boundaries. Chunks are small and focused so retrieval returns
precise policy sections, not whole documents.

## 3. Deterministic chunk IDs

`chunk_id = "<policy_id>#<section-slug>"`, e.g. `restricted-area#severity-guidance`.
Same policy → same IDs on every reindex, so:

- reindexing **upserts** (never duplicates),
- editing a policy updates its chunks in place,
- citations stay stable across reindexes.

## 4. Embedding model

`sentence-transformers/all-MiniLM-L6-v2` — local, CPU-only, no API keys.
384-dim vectors, L2-normalized. ~90 MB one-time download, cached in
`~/.cache/huggingface` afterwards. Exactly one model instance per process
(singleton in `backend/app/rag/embeddings.py`); ~200–400 MB RAM while loaded.

## 5. ChromaDB collection

- **Collection:** `guardx_policies` (deterministic name, cosine space)
- **Storage:** persistent local dir `backend/data/chroma/` (gitignored)
- ChromaDB is a **derived index**: it can be dropped and rebuilt from
  `policies/` at any time. PostgreSQL remains the source of truth.
- Works embedded — no separate ChromaDB server needed.

## 6. Retrieval process

`POST /api/v1/policies/search` → embed query → cosine top-k over the
collection (optional `policy_id` / `category` metadata filter) → chunks
ranked by relevance score `1 − distance/2` (0–1, higher is better).

## 7. API endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/policies/reindex` | Rebuild index from `policies/` → `{indexed_documents, indexed_chunks, collection, embedding_model, duration_ms}` |
| POST | `/api/v1/policies/search` | `{query, top_k, policy_id?, category?}` → ranked `RetrievedChunk[]` |
| GET | `/api/v1/policies` | Policy metadata list |
| GET | `/api/v1/policies/status` | RAG state: `unavailable` \| `initializing` \| `ready` \| `error` |
| GET | `/api/v1/policies/{policy_id}` | One policy's metadata |
| GET | `/api/v1/policies/{policy_id}/chunks` | A policy's chunks |

## 8. Example query

```json
POST /api/v1/policies/search
{"query": "A person entered the restricted server room without authorization", "top_k": 3}
```

Top hits (real run, 18.6 ms): all three from `restricted-area` —
`#recommended-response` (0.734), `#severity-guidance` (0.733),
`#purpose` (0.731). The severity-guidance chunk reads: "A person detected
inside a restricted zone without a matching access grant is a HIGH severity
event…". The event-derived query ("Unauthorized person entered the
restricted zone 'server room'…") returns `restricted-area#rules` at 0.814.

## 9. Citation validation

`backend/app/rag/citations.py`:

```python
validate_citations(retrieved_chunk_ids, cited_chunk_ids) -> bool
```

True iff every cited chunk was actually retrieved. LangGraph (Phase 6) will
call this before accepting an AI-generated incident report — the reasoning
layer can never cite a policy chunk it was not given.

## 10. Event → query (Phase 5/6 prep)

`backend/app/rag/event_query.py::zone_event_to_query(event)` converts a
`ZoneEvent` into retrieval text, e.g.:

> "Unauthorized person entered the restricted zone 'server room'. Person
> remained inside for 3.2 seconds. Which security policies apply, what
> severity guidance holds, and what is the recommended response?"

Descriptive only — no severity decision, no response action.

## 11. Reindex workflow (verified)

1. `POST /api/v1/policies/reindex` → 5 docs, 20 chunks.
2. Search → returns original content.
3. Edit `policies/restricted-area-policy.md` (add a rule).
4. Reindex → still 20 chunks (same IDs, updated content).
5. Search again → **updated content returned** (verified by test
   `test_policy_edit_reindex_updated_retrieval`).

## 12. Resource usage (measured on this VM, 2 vCPU, no GPU)

Model: `sentence-transformers/all-MiniLM-L6-v2`, 384-dim, CPU-only.

| Measurement | Value |
|---|---|
| One-time download | ~90 MB model (229 MB total HF cache with tokenizer) |
| Model load (cold) | ~22 s |
| Embed 20 chunks | ~1.5 s (~73 ms/chunk) |
| Full reindex (cold, incl. model load) | ~24.7 s → 5 docs, 20 chunks |
| Search end-to-end (warm) | ~19 ms (query embed + Chroma top-3) |
| Process RSS with model loaded | ~502 MB (Python + torch CPU + transformers + model) |

Warm reindexes skip the model load. torch stays the CPU-only build —
`sentence-transformers` reuses it; the CUDA wheel was never installed.
ChromaDB persistent dir `backend/data/chroma/` is a few hundred KB for
20 chunks.

## 13. Known limitations

- Semantic quality depends on the small MiniLM model; fine for 20 chunks,
  not a substitute for larger models at scale.
- No hybrid (keyword + vector) search; pure cosine similarity.
- Policy files are read from disk — no versioning/audit trail of edits
  (PostgreSQL policy table arrives in a later phase if needed).
- `where` filters are exact-match on `policy_id`/`category` only.
- First-ever reindex downloads the ~90 MB model (needs internet once).
- The dashboard panel has no policy editor — edit files, then reindex.

## 14. Module map

```
backend/app/rag/
  loader.py       policy .md + front-matter parsing
  chunker.py      deterministic section chunking
  embeddings.py   local MiniLM singleton (injectable for tests)
  store.py        persistent ChromaDB wrapper
  service.py      PolicyRAGService: index / search / status
  event_query.py  ZoneEvent -> retrieval query
  citations.py    citation-integrity validation
  schemas.py      PolicyChunk, PolicySearchRequest/Result, RetrievedChunk,
                  PolicyCitation, IndexReport, RagStatus, PolicyMeta
```
