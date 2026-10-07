# GuardX — RAG Design (Phase 0)

## Role boundary (hard rule)

- **RAG does:** turn policy documents into searchable chunks, embed them,
  retrieve top-k relevant chunks for an incident query.
- **RAG does NOT:** classify, decide severity, or recommend actions.
  Decisions come only from the LangGraph `reason` node.

## Pipeline

```
policies/*.md ──▶ ingester ──▶ chunk ──▶ embed ──▶ ChromaDB (guardx_policies)
                                              ▲
incident query ──▶ embed ──▶ similarity search (top-k=3) ──▶ RetrievedPolicy[]
```

## Corpus — the 5 initial policies

Stored as markdown in `policies/` (written in Phase 4). Each file has
`# Title`, `##` sections, and a YAML front-matter block
(`title`, `category`, `version`). Draft scope per policy:

1. **`restricted-area-policy.md`** (`category: restricted_area`)
   - Purpose & scope; what counts as a restricted area; authorization
     requirements; entry-response procedure (verify → challenge → escalate);
     severity guidance (after-hours entry = high).
2. **`after-hours-access-policy.md`** (`category: after_hours`)
   - After-hours definition (default 20:00–06:00, configurable); who may enter;
     logging requirements; intrusion during after-hours escalates severity.
3. **`visitor-policy.md`** (`category: visitor`)
   - Visitor registration, escort rule, badge visibility; unescorted visitor
     in restricted area = treat as unauthorized until verified.
4. **`emergency-response-policy.md`** (`category: emergency`)
   - When to call emergency services vs. internal guard; evacuation triggers;
     do-not-confront rule for operators.
5. **`incident-reporting-policy.md`** (`category: reporting`)
   - What every report must contain; retention; who gets notified at each
     severity; reprocessing rule.

## Chunking

- Split on `##` sections; target 300–500 tokens, 50-token overlap.
- Metadata per chunk: `{ policy_title, category, section, version, chunk_id }`
  where `chunk_id = "{slug}#{section-slug}"` — this is what the LLM must cite
  in `matched_policy`.
- Deterministic: re-running the ingester on unchanged files yields identical
  chunk IDs (needed for the citation check in the `reason` node).

## Embeddings & store

| Setting | Default (free/local) | Alternative |
|---------|---------------------|-------------|
| Provider | `sentence-transformers` | `openai` |
| Model | `all-MiniLM-L6-v2` (384-dim, ~90 MB) | `text-embedding-3-small` |
| Store | ChromaDB server (`chromadb` compose service) | embedded persistent client (`CHROMA_MODE=embedded`) |
| Collection | `guardx_policies` | — |
| Distance | cosine | — |

## Retrieval

- Query builder (in `retrieve_policies` node):
  `"{incident_type} {zone_name} detected at {hour}:00. Relevant security policy?"`
- `k=3`, no hard similarity cutoff in MVP (log scores; cutoff is a Phase 10
  tuning item).
- `POST /api/v1/policies/query` exposes raw retrieval for demoing RAG
  ("watch the policy come back before the AI reasons").

## Reindexing

`POST /api/v1/policies/reindex`: wipes the collection, re-ingests all
`policies/*.md`, returns `{ chunks_indexed }`. Run it after any policy edit —
the FYP demo of "policy-aware AI" is: edit policy → reindex → reprocess
incident → new decision.
