# GuardX — Architecture & Technology Decisions (Phase 0)

## 1. Final architecture

### 1.1 Data-flow (the required pipeline)

```
┌──────────────┐   frames    ┌──────────────┐  detections   ┌──────────────┐
│ Camera /     │ ──────────▶ │   Vision     │ ────────────▶ │ Zone Engine  │
│ Sample Video │  (OpenCV)   │ (YOLOv8n)    │  person bbox  │ (polygons)    │
│ file/rtsp/   │             │ person only  │  + track_id   │ dwell+cooldown│
│ webcam       │             └──────────────┘               └──────┬───────┘
└──────────────┘                                                 │ ZoneViolationEvent
                                                                 ▼
                                                        ┌────────────────┐
                                                        │ Incident Svc   │──▶ PostgreSQL
                                                        │ (structured    │    (incidents)
                                                        │  incident)     │
                                                        └───────┬────────┘
                                                                ▼
                                              ┌─────────────────────────────────┐
                                              │ LangGraph Incident Workflow     │
                                              │  validate → retrieve_policies   │
                                              │  (RAG/ChromaDB) → reason (LLM   │
                                              │  via LangChain) → build_report  │
                                              │  → persist → notify             │
                                              └────────┬───────────┬────────────┘
                                                       │           │ webhook
                                                       ▼           ▼
                                              ┌──────────────┐ ┌─────────┐
                                              │ Next.js      │ │   n8n   │ (optional)
                                              │ Dashboard    │ │ notify  │
                                              │ (SSE live)   │ └─────────┘
                                              └──────────────┘
```

### 1.2 Runtime topology (Docker Compose)

| Service   | Image / build        | Purpose |
|-----------|----------------------|---------|
| `postgres`| `postgres:16-alpine` | System of record: cameras, zones, incidents, reports, notifications |
| `backend` | built from `backend/`| FastAPI: vision loop, zone engine, incidents API, RAG, LangGraph |
| `frontend`| built from `frontend/`| Next.js dashboard (TypeScript + Tailwind) |
| `chromadb`| `chromadb/chroma`    | Vector store for security-policy RAG |
| `n8n`     | `n8nio/n8n`          | Optional notification automation (webhook receiver) |

Volumes: `pgdata` (PostgreSQL), `chroma-data` (vectors), `./assets` (videos/snapshots, bind mount).

No Redis in MVP: the backend uses an in-process async event bus + SSE fan-out.
This removes a service without losing the demo. Redis can be added later if the
vision loop is split into its own process.

### 1.3 Key design decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **YOLOv8n pretrained, person class only** (`ultralytics`) | No custom training in MVP; nano model runs on CPU at usable FPS on 8 GB RAM |
| 2 | **Zone engine consumes generic detection events** | `BaseEventDetector` interface: zone-intrusion is one detector; loitering etc. plug in later without touching the pipeline |
| 3 | **Zones = polygons in normalized 0–1 coords** | Resolution-independent; drawn once in the dashboard zone editor, work on any feed size |
| 4 | **Intrusion = bottom-center of bbox inside polygon + dwell time + cooldown** | Bottom-center ≈ feet on the ground; dwell (default 2 s) kills flicker; cooldown (default 60 s) prevents incident spam |
| 5 | **RAG retrieves only; LangGraph decides** | Hard architectural rule: the retriever returns policy chunks; the reasoning node + structured-output LLM produces `incident_type/severity/reason/matched_policy/recommended_action/report_summary` |
| 6 | **PostgreSQL is the source of truth; ChromaDB is a derived index** | Policies live in `policies/` + `policies` table; Chroma holds embeddings and is rebuilt via `POST /policies/reindex` |
| 7 | **LLM + embeddings fully env-configurable** | `LLM_PROVIDER` = openai/anthropic/google/ollama; `EMBEDDING_PROVIDER` = sentence-transformers/openai; default local/free (Ollama + MiniLM) so the demo costs $0 |
| 8 | **MJPEG annotated stream + snapshots** | Dashboard shows the live feed with zones/boxes drawn by the backend; snapshots stored per incident for the report |
| 9 | **SSE for live incident push** | Simpler than WebSockets for one-way server→dashboard events; `GET /api/v1/events/stream` |
| 10 | **n8n notified via webhook, fire-and-forget with retry** | Backend never blocks the incident pipeline on n8n; failure is logged in `notifications` table with `status=failed` |

## 2. Backend modules (`backend/app/`)

| Module | Responsibility | Key contents (Phase target) |
|--------|---------------|-----------------------------|
| `core/` | App wiring | `config.py` (pydantic-settings from env), `logging.py`, `security.py` |
| `api/v1/routers/` | HTTP surface | `health.py`, `cameras.py`, `zones.py`, `incidents.py`, `policies.py`, `stream.py`, `events.py`, `notifications.py` |
| `vision/` | CV pipeline | `frame_source.py` (file/RTSP/webcam via OpenCV), `detector.py` (YOLO wrapper, person filter), `tracker.py` (centroid track IDs), `events.py` (`BaseEventDetector` interface + registry) |
| `zone_engine/` | Restricted zones | `zone.py` (polygon model), `engine.py` (point-in-polygon, dwell, cooldown → `ZoneViolationEvent`) |
| `incidents/` | Incident lifecycle | `service.py` (create/update/acknowledge/resolve; triggers graph run) |
| `rag/` | Policy retrieval | `ingester.py` (md → chunks → Chroma), `store.py` (Chroma client), `retriever.py` (top-k query), `embeddings.py` (provider switch) |
| `graph/` | LangGraph workflow | `state.py` (`IncidentState`), `nodes.py` (6 nodes), `workflow.py` (StateGraph assembly) |
| `services/` | Cross-cutting | `notification.py` (n8n webhook), `sse.py` (event bus), `snapshots.py` |
| `models/` | SQLAlchemy ORM | `camera.py`, `zone.py`, `incident.py`, `incident_event.py`, `incident_report.py`, `policy.py`, `notification.py` |
| `schemas/` | Pydantic I/O | request/response models per router |
| `utils/` | Helpers | `geometry.py` (point-in-polygon), `time.py` |

## 3. Frontend modules (`frontend/`)

| Area | Contents |
|------|----------|
| `app/page.tsx` | Main dashboard: live feed, stats, recent incidents |
| `app/incidents/page.tsx` | Incident list (filter by severity/status) |
| `app/incidents/[id]/page.tsx` | Incident detail: snapshot, timeline of graph steps, AI decision card, report |
| `app/zones/page.tsx` | Zone editor: draw/edit polygons over camera frame |
| `app/policies/page.tsx` | Policy list (read-only view of indexed policies) |
| `components/` | `VideoFeed.tsx` (MJPEG img), `IncidentCard.tsx`, `SeverityBadge.tsx`, `ZoneEditor.tsx` (canvas), `IncidentTimeline.tsx`, `StatsCards.tsx` |
| `lib/` | `api.ts` (typed fetch client), `sse.ts` (EventSource hook), `types.ts` (shared TS types mirroring backend schemas) |

## 4. Docker services (compose definition — written in Phase 1)

- `postgres`: `postgres:16-alpine`, volume `pgdata`, healthcheck `pg_isready`.
- `backend`: `python:3.11-slim` build, runs `uvicorn app.main:app`; depends on postgres+chromadb (healthy); mounts `./assets`.
- `frontend`: `node:20-alpine` build, `next start`; `NEXT_PUBLIC_API_URL` → backend.
- `chromadb`: `chromadb/chroma:latest`, volume `chroma-data`, port 8001→8000 (host mapping avoids clashing with backend's 8000).
- `n8n`: `n8nio/n8n`, profile-gated so it only starts with `--profile automation` (keeps default `up` lean).

## 5. Dependencies

**Backend (`requirements.txt`, Phase 1 pins):**
`fastapi`, `uvicorn[standard]`, `sqlalchemy`, `alembic`, `psycopg2-binary`,
`pydantic`, `pydantic-settings`, `ultralytics`, `opencv-python-headless`,
`numpy`, `pillow`, `langchain`, `langchain-core`, `langchain-openai`,
`langchain-anthropic`, `langchain-google-genai`, `langchain-ollama`,
`langgraph`, `chromadb`, `sentence-transformers`, `httpx`, `python-multipart`,
`pytest`, `httpx` (test client).

**Frontend (`package.json`):** `next`, `react`, `react-dom`, `typescript`,
`tailwindcss`, `@types/*`. No heavy chart lib in MVP (CSS/SVG stats suffice).

## 6. Risks & technical limitations

| Risk | Impact | Mitigation |
|------|--------|------------|
| CPU-only YOLO on 8 GB RAM too slow | Missed detections / laggy demo | yolov8n @640px, `FRAME_SKIP=2`, single camera in MVP; document measured FPS in Phase 2 |
| LLM latency/cost blocks pipeline | Slow incident resolution | Default local Ollama; async graph run decoupled from detection loop; timeouts + fallback severity rule |
| LLM hallucinates policy | Wrong decision basis | Prompt forces citation of retrieved chunks; `matched_policy` must be one of retrieved chunk IDs; human-readable report shows sources |
| Chroma version drift | Ingest breaks | Pin `chromadb` version; reindex endpoint rebuilds collection deterministically |
| RTSP streams unstable | Demo flakiness | Phase 2–3 use sample video files; RTSP/webcam marked experimental |
| n8n optional & external | Notification silently fails | Webhook fire-and-forget + retry; `notifications` table records every attempt |
| Small/distant persons missed by pretrained model | False negatives | Documented MVP limitation; no custom training until Phase 10+; confidence threshold tunable per camera |
| Multi-camera scale | Vision loop is per-process | MVP = 1 active camera; architecture allows one worker per camera later |

**Explicit non-goals for MVP:** custom YOLO training, facial recognition,
multi-camera orchestration, PTZ control, mobile app, auth/RBAC (single-operator
demo; note as future work in the FYP report).
