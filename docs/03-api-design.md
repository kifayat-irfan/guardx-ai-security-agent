# GuardX — API Design (Phase 0)

Base path: `/api/v1`. JSON everywhere. Errors: `{ "detail": "..." }` with
proper HTTP codes. Interactive docs at `/docs` (Swagger) in dev.

## Health
- `GET /health` → `{ "status": "ok", "version": "0.1.0" }`
- `GET /api/v1/health/detailed` → `{ postgres, chroma, yolo_model_loaded }`

## Cameras
- `GET /api/v1/cameras` → list
- `POST /api/v1/cameras` — body `{ name, source_type, source_url }` → 201 camera
- `GET /api/v1/cameras/{id}` → camera + its zones
- `PATCH /api/v1/cameras/{id}` — `{ name?, status? }`
- `DELETE /api/v1/cameras/{id}`
- `POST /api/v1/cameras/{id}/start` — begin vision loop for this camera
- `POST /api/v1/cameras/{id}/stop`

## Zones
- `GET /api/v1/cameras/{camera_id}/zones` → list
- `POST /api/v1/cameras/{camera_id}/zones` — body:
  ```json
  { "name": "Server Room Door",
    "polygon": [[0.60,0.30],[0.85,0.30],[0.85,0.90],[0.60,0.90]],
    "dwell_seconds": 2.0, "cooldown_seconds": 60, "active": true }
  ```
- `PATCH /api/v1/zones/{id}` — update polygon / thresholds / active
- `DELETE /api/v1/zones/{id}`

## Stream (video)
- `GET /api/v1/cameras/{id}/stream` — MJPEG multipart stream with zones + boxes drawn
- `GET /api/v1/cameras/{id}/snapshot` — single JPEG frame (used by zone editor)

## Incidents
- `GET /api/v1/incidents?status=open&severity=high&limit=50` → list (newest first)
- `GET /api/v1/incidents/{id}` → incident + report + events timeline
- `PATCH /api/v1/incidents/{id}` — `{ "status": "acknowledged" | "resolved" }`
- `POST /api/v1/incidents/{id}/reprocess` — re-run the LangGraph workflow
  (demo-friendly: tweak a policy, re-run, show the new decision)
- `POST /api/v1/incidents/{id}/notify` — manually trigger n8n notification

## Policies (RAG source)
- `GET /api/v1/policies` → list (title, category, version)
- `GET /api/v1/policies/{id}` → full content
- `POST /api/v1/policies/reindex` — re-chunk + re-embed into ChromaDB → `{ chunks_indexed: N }`
- `POST /api/v1/policies/query` — body `{ "query": "...", "k": 3 }` → raw retrieval results (debug/RAG demo)

## Live events
- `GET /api/v1/events/stream` — Server-Sent Events:
  `incident.created`, `incident.updated`, `graph.step`, `notification.sent`

## Notifications
- `GET /api/v1/notifications?incident_id=...` → attempts log

## Shared TypeScript types

`frontend/lib/types.ts` mirrors the Pydantic schemas 1:1
(`Camera`, `Zone`, `Incident`, `IncidentReport`, `IncidentDecision`,
`PolicyChunk`). Any schema change updates both — checked in Phase 8 tests.
