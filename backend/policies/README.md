# Security policy corpus (RAG source of truth)

The 5 policy documents live here as Markdown with YAML front-matter
(`title`, `category`, `version`). Written in **Phase 4**; draft scope is
defined in `docs/05-rag-design.md`.

Files to create in Phase 4:
- `restricted-area-policy.md` (category: `restricted_area`)
- `after-hours-access-policy.md` (category: `after_hours`)
- `visitor-policy.md` (category: `visitor`)
- `emergency-response-policy.md` (category: `emergency`)
- `incident-reporting-policy.md` (category: `reporting`)

They are indexed into ChromaDB via `POST /api/v1/policies/reindex`.
Edit a policy → reindex → reprocess an incident → watch the AI decision change.
