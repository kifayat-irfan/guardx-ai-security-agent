# GuardX — AI Autonomous Security Agent

Real-time incident detection and response for physical security.

**Scenario:** a person enters a restricted area → YOLO detects the person →
centroid tracking assigns an ID → the zone engine flags the intrusion → a
LangGraph workflow retrieves the relevant security policy (RAG via LangChain),
an LLM reasons over incident + policy, classifies severity, and the validated
decision is persisted to PostgreSQL → the Next.js dashboard streams the
incident live (SSE) → n8n optionally fires automation webhooks.

**Status: all 10 phases complete and verified** (see git log for phase
commits). When no LLM is available the system reports `llm_unavailable`
honestly — it never invents AI results.

## Team

| Member       | Role                          |
|--------------|-------------------------------|
| Kifayat Irfan  | Lead — AI / backend / LangGraph |
| Abdur Razzaq   | Computer Vision / zone engine   |
| Abdur Rehman   | Frontend (Next.js) / n8n        |

## Architecture

```
Camera / video file
  → YOLOv8n person detection (app/vision)
  → Centroid tracker
  → Restricted-zone engine (polygons, dwell, cooldown)
  → ZoneEvent
  → LangGraph workflow (6 nodes: validate → query → retrieve → analyze → validate → decide)
  → LangChain retriever + policy tool over ChromaDB RAG (5 policies, 20 chunks)
  → Decision validation (citations ⊆ retrieved, severity enum)
  → PostgreSQL: incidents + incident_reports (atomic, migration 20261007_0003)
  → SSE live stream (/api/v1/events/stream) → Next.js dashboard
  → n8n webhook (optional, fire-and-forget, failure-isolated)
```

Key boundary: **RAG retrieves, LangGraph decides, PostgreSQL is the source
of truth.** ChromaDB is a rebuildable derived index.

## Main features

- YOLOv8n person detection + centroid tracking + camera API/worker + MJPEG
- Restricted-zone polygons with dwell/cooldown, enter/exit events
- Security-policy RAG (local MiniLM embeddings, persistent ChromaDB)
- LangChain retriever/tool/prompt integration, optional Ollama LLM
- LangGraph incident workflow with explicit terminal failure states
- Incident persistence + AI reports in PostgreSQL, reprocess-in-place
- Live SSE dashboard: overview, live feed, cameras, policies, incidents, health
- n8n automation webhooks (severity-aware, shared-secret auth, disabled by default)
- Health monitoring for every subsystem (never faked)

## Tech stack

- **Backend:** FastAPI, SQLAlchemy + Alembic, PostgreSQL 16
- **AI:** Ultralytics YOLOv8n, LangChain, LangGraph, ChromaDB, sentence-transformers (all-MiniLM-L6-v2), optional Ollama
- **Frontend:** Next.js 16, React 19, TypeScript, Tailwind, Vitest
- **Automation:** n8n (profile-gated in Docker Compose)

## Setup

```bash
# 1. PostgreSQL 16 with database + user (see docs/07-phase1-commands.md)
# 2. Python backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

# 3. Frontend
cd ../frontend
npm install
```

## Configuration

Copy `.env.example` to `.env` (repo root). Important variables:

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://guardx:change_me_in_production@localhost:5432/guardx` | Postgres |
| `GUARDX_REAL_EMBEDDINGS` | unset | set `=1` for real MiniLM embeddings |
| `N8N_ENABLED` | `false` | n8n webhook master switch |
| `N8N_WEBHOOK_URL` | `""` | e.g. `http://n8n:5678/webhook/guardx-incident` |
| `N8N_WEBHOOK_SECRET` | `""` | sent as `X-GuardX-Webhook-Secret` |
| `N8N_WEBHOOK_TIMEOUT_SECONDS` | `5.0` | webhook POST timeout |

No hardcoded secrets. n8n stays optional: `docker compose --profile automation up`.

## Running

```bash
# backend (from backend/)
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

# frontend (from frontend/)
npm run dev        # http://localhost:3000 (set NEXT_PUBLIC_API_URL)
```

## Demo (MVP)

Automated driver (needs a running backend):

```bash
python scripts/demo_guardx.py --base-url http://localhost:8000
```

It checks health, ensures policies are indexed, submits a `zone_enter`
event, runs the full analysis pipeline, verifies history/detail/reprocess,
and reports PASS. For the live camera path: open the dashboard, start a
camera on `assets/test_videos/person_pan_test.mp4`, draw a restricted zone,
and watch the Live Feed (auto-analyze is on by default).

## Testing

```bash
# backend: 198 tests (incl. E2E MVP + n8n isolation)
cd backend && .venv/bin/python -m pytest tests/ -q

# frontend: 11 Vitest tests + production build
cd frontend && npx vitest run && npm run build
```

## Documentation

`docs/01-architecture.md` … `docs/07-phase1-commands.md` (design),
`docs/09-phase3-restricted-zone.md`, `docs/10-phase4-rag.md`,
`docs/11-phase5-langchain.md`, `docs/12-phase6-langgraph.md`,
`docs/13-phase7-persistence.md`, `docs/14-phase8-dashboard.md`,
`docs/15-phase9-n8n.md`, `docs/16-phase10-final-verification.md`.

## Design principles

1. **RAG retrieves, it never decides.** Policy text is context; the LangGraph
   reasoning node produces the structured decision.
2. **PostgreSQL is the source of truth** for incidents and reports.
3. **Configurable AI.** LLM and embedding providers switch via env vars only.
4. **No fake completeness.** A feature is done only when its tests pass —
   and failures stay visible (`llm_unavailable`, never a fake success).

## Limitations (honest)

- CPU-only development target; YOLOv8n ≈ 100 ms/frame on 2 vCPUs
- No Ollama on the dev box → AI analysis reports `llm_unavailable`; no fake results
- In-process SSE event bus (single worker); SSE does not replay history
- n8n delivery is at-most-once, fire-and-forget; workflow nodes are placeholders until real credentials are wired in n8n
- Centroid tracker: simple, can ID-switch on occlusion
- English-only policy documents
- FYP prototype, not production-hardened (no API auth, no TLS, no multi-worker)
