# GuardX — Phased Implementation Plan (Phase 0)

Rule for every phase: **the phase is done only when its exit criteria and
tests pass.** Demos use real numbers (FPS, latency, chunk counts) — never
placeholders.

---

## Phase 1 — Project foundation: FastAPI + Next.js + Docker
**Goal:** `docker compose up` brings up postgres, backend (`/docs` live),
frontend (renders), chromadb.

**Work:** write `docker-compose.yml`, `backend/Dockerfile`,
`frontend/Dockerfile`, `requirements.txt`, `package.json`, FastAPI app with
`/health` + `/api/v1/health/detailed`, Alembic with first migration
(cameras, zones, policies), Next.js scaffold with Tailwind calling the health
endpoint, `.env` from `.env.example`.

**Exit criteria:** `docker compose up --build` succeeds; backend docs load;
frontend shows "backend: ok"; `alembic upgrade head` clean.

**Tests:**
- `pytest backend/tests/test_health.py` — `/health` returns 200 + version.
- Migration up/down round-trip on a scratch DB.
- Frontend smoke: page renders backend status (manual check).

## Phase 2 — YOLO video detection
**Goal:** given a sample video, the backend detects persons frame-by-frame.

**Work:** `vision/frame_source.py` (file source), `vision/detector.py`
(YOLOv8n wrapper, person class=0, confidence filter), `vision/tracker.py`
(centroid track IDs), `POST /cameras/{id}/start|stop`,
`GET /cameras/{id}/stream` (MJPEG with boxes), FPS + detection log endpoint.

**Exit criteria:** sample video plays annotated in the dashboard; measured
FPS documented; single camera only.

**Tests:**
- Unit: detector finds person in a fixture image (ship one test image with a
  clearly visible person) with confidence ≥ threshold.
- Unit: tracker keeps stable IDs across 30 synthetic frames.
- Perf: log FPS @640px, FRAME_SKIP=2 on the dev machine; record in docs.

## Phase 3 — Restricted-zone detection
**Goal:** entering a drawn polygon fires exactly one `ZoneViolationEvent`.

**Work:** `zone_engine/` (point-in-polygon on bbox bottom-center, dwell,
cooldown), zone CRUD API, `ZoneEditor.tsx` canvas component, snapshot save
on violation.

**Exit criteria:** draw a zone → walk a person through it in the sample video
→ one event, one snapshot; re-entry within cooldown does not refire.

**Tests:**
- Unit: point-in-polygon (inside/outside/edge cases) — `test_geometry.py`.
- Unit: dwell (fires only after N s inside), cooldown (no refire), exit/reset
  — simulated detection sequences, no video needed.
- Integration: sample video with scripted zone → exactly 1 violation event.

## Phase 4 — RAG + ChromaDB + security policies
**Goal:** the 5 policies are indexed and retrievable.

**Work:** write the 5 `policies/*.md` files, `rag/ingester.py`,
`rag/store.py`, `rag/retriever.py`, `rag/embeddings.py`,
`POST /policies/reindex`, `POST /policies/query`.

**Exit criteria:** reindex reports the expected chunk count; query
"unauthorized person entered restricted area at night" returns the Restricted
Area Policy chunk as top-1.

**Tests:**
- Ingest test: 5 files → expected chunk count, deterministic chunk IDs.
- Retrieval test: 3 canned queries → expected top-1 policy each.
- Reindex idempotence: run twice → same chunk count, no duplicates.

## Phase 5 — LangChain integration
**Goal:** one provider-switchable chat model + structured output, tested free.

**Work:** `rag/llm.py` → `get_chat_model()` factory
(openai/anthropic/google/ollama), `IncidentDecisionSchema` Pydantic model,
prompt template for the reasoning step, mock LLM for tests.

**Exit criteria:** same prompt returns a valid `IncidentDecisionSchema`
against Ollama (local, $0) and at least one cloud provider.

**Tests:**
- Structured-output test with a fake/mock model: output validates against
  the schema (no network, no cost).
- Manual: one real call per configured provider; record latency + cost.

## Phase 6 — LangGraph incident workflow
**Goal:** a `ZoneViolationEvent` runs the full graph and produces a decision.

**Work:** `graph/state.py`, `graph/nodes.py` (6 nodes), `graph/workflow.py`,
`incident_events` audit writes, incident service triggers graph (background
task, decoupled from the vision loop), `POST /incidents/{id}/reprocess`.

**Exit criteria:** end-to-end on a synthetic incident: all 6 nodes execute,
timeline rows exist, decision has all 6 required fields with
`matched_policy` citing a real retrieved chunk.

**Tests:**
- Graph test with mocked LLM + stub retriever: assert node order, decision
  fields, DB writes (`incidents`, `incident_events`).
- Citation test: `matched_policy` not in retrieved chunk IDs → node retries /
  falls back (assert fallback path).
- Error-path test: retriever returns [] → decision has `matched_policy="none"`.

## Phase 7 — Incident reports + PostgreSQL
**Goal:** every incident gets a persisted, human-readable report.

**Work:** `incident_reports` table + migration, `build_report` markdown
template, report section in `GET /incidents/{id}`, acknowledge/resolve
endpoints.

**Exit criteria:** incident detail API returns incident + report + event
timeline; status transitions work.

**Tests:**
- Report content test: markdown contains severity, reason, matched policy,
  recommended action, summary.
- API tests: create → acknowledge → resolve lifecycle; 404 on unknown id.

## Phase 8 — Next.js security dashboard
**Goal:** the demo UI: live feed, incidents, zones, policies.

**Work:** pages + components per `docs/01-architecture.md` §3, SSE hook for
live incidents, `lib/types.ts` mirrored from backend schemas.

**Exit criteria:** full demo flow clickable: watch feed → incident appears
live with severity badge → open detail → timeline + report → draw a new zone.

**Tests:**
- Type-parity check: backend schema JSON vs `types.ts` (script or test).
- SSE test: trigger synthetic incident → dashboard receives event (manual).
- Manual UI pass on desktop + one mobile width.

## Phase 9 — n8n notification automation
**Goal:** incident → n8n webhook → external notification (e.g. Telegram/email).

**Work:** `services/notification.py` (webhook, timeout, retry, logging),
`n8n/workflows/guardx-incident-notify.json` export, `N8N_ENABLED` gating,
`POST /incidents/{id}/notify`.

**Exit criteria:** with n8n profile up, a high-severity incident produces a
real external message; failure recorded in `notifications` table.

**Tests:**
- Webhook test against a local mock receiver: payload shape asserted.
- Failure test: bad URL → `status=failed` row, pipeline still completes.
- Manual: real n8n workflow delivers one end-to-end notification.

## Phase 10 — Testing, documentation, demo preparation
**Goal:** FYP-ready: reliable demo + report material.

**Work:** full `docker compose --profile automation up` rehearsal, demo
script (timed), sample videos curated, architecture diagrams finalized,
README quickstart verified from scratch, FYP report outline
(problem, architecture, AI design, tests, limitations, future work),
tuning pass (similarity cutoff, dwell defaults) from measured data.

**Exit criteria:** clean-machine run works; demo runs without intervention;
every phase's tests green.

**Tests:**
- Full suite: `pytest` backend, `tsc --noEmit` + build frontend.
- Soak test: 10-minute single-camera run → incident count sane, no memory
  growth, no duplicate incidents.
- Demo dry-run checklist signed off by all 3 team members.

---

## Suggested team split

| Phase | Kifayat (AI/backend) | Abdur Razzaq (vision) | Abdur Rehman (frontend/n8n) |
|-------|----------------------|----------------------|------------------------------|
| 1 | backend scaffold, compose | — | Next.js scaffold |
| 2–3 | API wiring | detector, tracker, zone engine | stream view, zone editor |
| 4–6 | RAG, LangChain, LangGraph | — | policy/query debug UI |
| 7–8 | reports API | — | dashboard pages |
| 9–10 | hardening, tests | perf tuning | n8n, demo prep |
