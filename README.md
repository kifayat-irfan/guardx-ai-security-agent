# GuardX — AI Autonomous Security Agent

**Real-Time Incident Detection, Policy-Grounded AI Analysis, and Automated Security Response**

A final-year project: an end-to-end autonomous security agent that watches a
camera feed, detects a person entering a restricted zone, retrieves the
relevant security policy, asks a real LLM to reason over the incident with
policy citations, persists the validated decision, and streams everything to a
live dashboard — with optional n8n automation.

**▶ Watch the Final Demo:** [`demo/GuardX-Final-Demo-V3.mp4`](demo/GuardX-Final-Demo-V3.mp4)
(2:35 — full real pipeline, real SenseNova AI analysis)

---

## 1. Project Overview

GuardX turns an ordinary camera into an autonomous security analyst. Instead of
a human watching hours of footage, the system detects people with YOLO, tracks
them through restricted zones, and — when an intrusion occurs — runs a
stateful AI workflow that grounds its judgment in the site's own security
policies. The result is a structured incident: severity classification,
policy-cited reasoning, and a recommended action, stored as the permanent
record.

## 2. Why GuardX

- **Speed:** threats strike in seconds; GuardX detects, understands, and
  responds in real time.
- **Grounding:** the AI reasons over retrieved policy documents, not vibes —
  every analysis carries citations.
- **Honesty:** if the LLM is unavailable, the system reports
  `llm_unavailable` instead of inventing results.
- **Auditability:** PostgreSQL holds every incident and AI report; reprocessing
  is idempotent, never duplicated.

## 3. Core Features

- YOLOv8n person detection + centroid tracking + camera API/worker + MJPEG feed
- Restricted-zone polygons with dwell and cooldown rules; enter/exit events
- Security-policy RAG (local MiniLM embeddings, persistent ChromaDB)
- LangChain retriever/tool/prompt integration
- LangGraph stateful incident workflow (6 nodes) with explicit failure states
- **Real SenseNova AI analysis** (`sensenova-6.8-flash-lite`) with decision
  validation (citations ⊆ retrieved chunks, severity enum)
- Incident + AI report persistence in PostgreSQL; reprocess-in-place
- Live SSE dashboard: overview, live feed, cameras, policies, incidents, health
- n8n automation webhooks (severity-aware, shared-secret auth, disabled by
  default)
- Health monitoring for every subsystem

## 4. System Architecture

```mermaid
flowchart LR
    A[Camera / Video] --> B[YOLO Detection]
    B --> C[Centroid Tracker]
    C --> D[Restricted Zone Engine]
    D --> E[Security Event]
    E --> F[RAG Policy Retrieval]
    F --> G[LangGraph Workflow]
    G --> H[SenseNova AI]
    H --> I[Validated Decision]
    I --> J[(PostgreSQL)]
    J --> K[Dashboard / SSE]
    E --> L[n8n Automation]
```

**Boundaries:**

- **YOLO** detects people/objects.
- **Tracker** maintains temporary identities across frames.
- **Zone Engine** detects restricted-area entry/exit.
- **RAG** retrieves relevant security policies — it never decides.
- **LangChain** connects retrieval, tools, and LLM components.
- **LangGraph** controls the stateful incident workflow.
- **SenseNova** performs the real AI analysis.
- **PostgreSQL** is the source of truth.
- **ChromaDB** is the derived, rebuildable policy index.
- **n8n** is an optional automation layer.

## 5. End-to-End Workflow

1. Camera/video → YOLO detects people; the centroid tracker assigns IDs.
2. Zone engine checks positions against restricted polygons (dwell + cooldown).
3. A `zone_enter` event fires → the LangGraph workflow starts.
4. **validate** → **query** (build retrieval query) → **retrieve** (RAG over
   ChromaDB, 5 policies / 20 chunks).
5. **analyze** → real SenseNova API call: severity, reasoning with policy
   citations, recommended action.
6. **validate** → decision checked (citations must come from retrieved chunks;
   severity must be a valid enum).
7. **decide** → atomic PostgreSQL write: incident + AI report; SSE broadcast to
   the dashboard.
8. Optional: n8n webhook fires for automation (disabled by default).

## 6. Technology Stack

- **Language:** Python, TypeScript
- **Backend:** FastAPI, SQLAlchemy, Alembic
- **Vision:** YOLO (Ultralytics), OpenCV
- **AI:** SenseNova (`sensenova-6.8-flash-lite`), LangChain, LangGraph, RAG,
  ChromaDB, Sentence Transformers (all-MiniLM-L6-v2)
- **Data:** PostgreSQL 16
- **Frontend:** Next.js, React, Tailwind, SSE live stream
- **Automation:** n8n
- **Infra:** Docker, pytest, Vitest

## 7. Real SenseNova AI Integration

GuardX performs genuine incident analysis through the SenseNova international
API (`https://token.sensenova.ai/v1`) with model
`sensenova-6.8-flash-lite`. Nothing is mocked: the workflow sends the event
context plus retrieved policy chunks and receives back a real severity
classification, policy-grounded reasoning, and citations. If the LLM is
unavailable, the incident honestly records `llm_unavailable`.

## 8. Computer Vision Pipeline

- Ultralytics YOLOv8n person detection (CPU-oriented for the FYP environment)
- Centroid tracker for short-term identity across frames
- Restricted-zone engine: polygons, dwell seconds, cooldown seconds
- Camera worker with MJPEG streaming; cameras configurable per zone

## 9. RAG / Policy Retrieval

- 5 security policy documents, 20 chunks, embedded with local
  all-MiniLM-L6-v2 (free, no API key)
- Persistent ChromaDB index; rebuildable with
  `POST /api/v1/policies/reindex`
- LangChain retriever + policy tool feed the reasoning node

## 10. LangChain + LangGraph

- LangChain wires retriever, policy tool, prompt template, and LLM client.
- LangGraph runs the 6-node incident workflow:
  `validate → query → retrieve → analyze → validate → decide`
  with explicit terminal failure states.

## 11. PostgreSQL Incident Persistence

- `incidents` + `incident_reports` tables (Alembic migration `20261007_0003`)
- Atomic writes; PostgreSQL is the source of truth
- Reprocess-in-place: re-analyzing an incident never creates a duplicate

## 12. Real-Time Dashboard / SSE

Next.js dashboard streams incidents live via Server-Sent Events
(`/api/v1/events/stream`): overview, live feed, cameras, policies, incidents,
and per-subsystem health. SSE does not replay history — history comes from
PostgreSQL.

## 13. n8n Automation

Optional severity-aware webhook delivery with shared-secret auth
(`X-GuardX-Webhook-Secret`), fire-and-forget and failure-isolated.
Disabled by default (`N8N_ENABLED=false`). In the final demo it is honestly
shown as disabled — no notification claims are faked.

## 14. Demo

**▶ [Watch the Final Demo](demo/GuardX-Final-Demo-V3.mp4)** (~2:35)

The V3 demo demonstrates the complete real pipeline: live YOLO detections →
real `zone_enter` event → RAG retrieval → real SenseNova API response with
**HIGH severity**, policy-grounded reasoning, and real policy citations →
PostgreSQL persistence → live dashboard → idempotent reprocess → n8n shown
disabled. A clean unedited recording is also available on request.

## 15. Screenshots

See the demo video for real dashboard visuals. No fabricated screenshots are
included in this repository.

## 16. Project Structure

```
guardx/
├── backend/               # FastAPI app
│   ├── app/api/v1/routers # cameras, zones, policies, incidents, events, health
│   ├── app/vision/        # YOLO + tracker + zone engine
│   ├── app/graph/         # LangGraph workflow nodes
│   ├── app/langchain/     # retriever, tools, prompts, SenseNova client
│   ├── app/incidents/     # service, repository, schemas
│   ├── app/automation/    # n8n webhook service
│   └── alembic/           # migrations
├── frontend/              # Next.js dashboard (TypeScript, Tailwind)
├── scripts/
│   ├── demo_guardx.py     # end-to-end MVP verification driver
│   ├── record_demo_v3.py  # V3 demo recorder
│   └── build_demo_v3.py   # V3 demo video builder
├── demo/
│   └── GuardX-Final-Demo-V3.mp4
├── docs/                  # architecture + phase design docs
└── .env.example           # config template (placeholders only)
```

## 17. Local Setup

```bash
# 1. PostgreSQL 16 with database + user (see docs/07-phase1-commands.md)
# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

# 3. Frontend
cd ../frontend
npm install
```

## 18. Environment Variables

Copy `.env.example` to `.env` (repo root) and fill in your own values:

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://guardx:change_me_in_production@localhost:5432/guardx` | PostgreSQL |
| `LLM_PROVIDER` | `sensenova` | `sensenova` \| `openai` \| `anthropic` \| `google` \| `ollama` |
| `SENSENOVA_API_KEY` | `""` | your SenseNova key (never committed) |
| `SENSENOVA_MODEL` | `sensenova-6.8-flash-lite` | SenseNova model |
| `N8N_ENABLED` | `false` | n8n webhook master switch |
| `N8N_WEBHOOK_URL` | `""` | e.g. `http://n8n:5678/webhook/guardx-incident` |
| `N8N_WEBHOOK_SECRET` | `""` | sent as `X-GuardX-Webhook-Secret` |
| `N8N_WEBHOOK_TIMEOUT_SECONDS` | `5.0` | webhook POST timeout |

## 19. Running the System

```bash
# backend (from backend/)
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

# frontend (from frontend/)
npm run dev        # http://localhost:3000 (set NEXT_PUBLIC_API_URL)
```

Optional Docker: `docker compose --profile automation up` for the n8n stack.

## 20. Testing

```bash
# backend (from backend/)
.venv/bin/python -m pytest tests/ -q      # 215 passed, 1 skipped

# frontend (from frontend/)
npx vitest run                             # 11/11 passed
npm run build                              # production build green
```

## 21. Demo Verification

```bash
python scripts/demo_guardx.py --base-url http://localhost:8000
```

Verified MVP flow: `zone_enter` → RAG retrieval → real SenseNova analysis →
HIGH severity → PostgreSQL persistence → idempotent reprocess → no duplicate
incident. Result: **PASS**.

## 22. Team

- **Kifayat Irfan** — Backend, YOLO integration, restricted-zone engine, RAG,
  LangChain, LangGraph, FastAPI, SenseNova integration, PostgreSQL
  integration, final system integration.

## 23. Responsibilities

| Area | Owner |
|---|---|
| AI/backend, LangGraph, system integration | Kifayat Irfan |
| Computer vision support, test scenarios, documentation | Abdur Razzaq |
| Frontend dashboard, incident UI, n8n integration, frontend testing | Abdur Rehman |

## 24. Known Limitations

- CPU-oriented YOLO inference in the FYP environment (YOLOv8n ≈ 100 ms/frame
  on 2 vCPUs)
- Simple centroid tracking — can ID-switch on occlusion
- English-only policy documents
- In-process SSE event bus (single worker); SSE does not replay history
- n8n automation is optional and disabled by default
- No production API authentication / TLS layer
- FYP/prototype scope — not production security infrastructure

## 25. Security Notes

- Secrets live in environment variables only; `.env` is gitignored and never
  committed.
- `.env.example` contains placeholders only — no real credentials.
- API keys, webhook secrets, passwords, and tokens are never committed.
- Webhook secrets are not logged.
- Create your own credentials locally from `.env.example`.

## 26. License

MIT — see [LICENSE](LICENSE).

---

Built by Kifayat Irfan, Abdur Razzaq, and Abdur Rehman.
