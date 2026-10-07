# Phase 8 — Production Dashboard and Live Incident Stream

**Status: complete and verified (2026-10-07).**

> Phase 8 is frontend/dashboard work plus the live event presentation.
> No n8n, no notifications — those are Phase 9+.

## 1. Dashboard architecture

```
backend (FastAPI)
  ├─ REST: cameras / zones / policies / incidents / health
  └─ SSE:  GET /api/v1/events/stream   (zone_event | incident | heartbeat)
                ▲ published by camera workers + incidents API
Next.js dashboard
  ├─ lib/api.ts            typed REST client (API_URL configurable)
  ├─ lib/eventStream.ts    singleton SSE manager
  ├─ lib/useEventStream.ts React hook (refcounted, cleanup-safe)
  └─ components/*          section panels (HUD style)
```

## 2. Live event stream (backend)

- `app/events/bus.py` — in-process, thread-safe pub/sub (`EventBus`,
  module singleton `bus`). Slow consumers drop messages; publishers
  (camera loop, API) never block. Publish calls are wrapped in
  try/except so the stream can never break detection or persistence.
- `app/api/v1/routers/events.py` — `GET /api/v1/events/stream`,
  `text/event-stream`, `Cache-Control: no-cache`, 20 s `: heartbeat`
  comments. Generator unsubscribes on client disconnect.
- Publishers: `camera_worker` publishes every zone event
  (`zone_event` + full ZoneEvent JSON); `incidents` router publishes
  `incident` (id, status, severity, zone, summary, reprocessed flag)
  after analyze and after reprocess.

Test note: starlette's `TestClient` and httpx's `ASGITransport` buffer
the whole response, so infinite SSE cannot be tested in-process. The
event tests run uvicorn in a thread (same process → shared bus) and
stream over real sockets.

## 3. Live event stream (frontend)

- `eventStream` singleton: exactly one `EventSource` per page regardless
  of subscribers/rerenders (refcounted `connect()`/`release()`).
- Native `EventSource` auto-reconnect; connection state
  (`connecting|open|closed|error`) broadcast to subscribers.
- Duplicate protection: dedup by `event_id`/`incident_id`/`workflow_id`
  (bounded 500-entry set).
- `useEventStream(onMessage)` — subscribes on mount, unsubscribes and
  releases on unmount. `onMessage` must be `useCallback`-stable.

## 4. Dashboard sections

| Section | Anchor | Content |
|---|---|---|
| Header | — | GuardX brand, live clock, backend connection badge, Refresh |
| Overview | #overview | stat cards: cameras, people, zones, incidents, high/critical, system |
| Live feed | #live | zone events (ENTER highlighted) + incidents, auto-analyze toggle, connection badge |
| Cameras | #cameras | CRUD, start/stop, MJPEG stream, FPS/persons/tracking IDs/zones |
| Policies | #policies | RAG status, reindex, search (unchanged Phase 4/5) |
| Incidents | #incidents | history table + filters + detail + reprocess (Phase 7) |
| AI workflow | #workflow | manual run-workflow demo (Phase 6) |
| System health | #system | backend, Postgres, incident store, ChromaDB, LangChain, LangGraph, YOLO, n8n placeholder |

Sidebar anchor navigation (hidden on mobile), responsive grid
(2-col stats on tablet, 6-col on desktop).

## 5. Live incident feed + auto-analyze demo flow

The `LiveFeedPanel` implements the Phase 8 demo flow:

1. Start camera (file/RTSP) with restricted zones.
2. Person enters → worker publishes `zone_event` → feed shows ENTER.
3. Auto-analyze (toggle, default on) POSTs the event to
   `/incidents/analyze` (deduped per `event_id`).
4. Workflow runs; incident persisted; backend publishes `incident`.
5. Feed shows the incident; history panel picks it up on refresh.
6. If the LLM is unavailable, the feed shows the real
   `llm_unavailable` status — never a fake analysis.

Verified live against uvicorn: SSE connect → analyze
(`llm_unavailable`, honest on this box) → `incident` SSE event with
the incident id → history lists it → health reports real subsystem
states.

## 6. Health display

`HealthPanel` renders `GET /api/v1/health/detailed` verbatim:
ready/up, unavailable, initializing, error — never faked. n8n shows
`unavailable / not configured` as an explicit Phase 9 placeholder.

## 7. State management

React state only — no store library. Rules enforced:
- one shared `EventSource` (singleton, refcounted);
- bounded feed lists (30 items);
- overview refresh every 15 s, paused when tab hidden;
- effects clean up subscriptions/timers/listeners.

## 8. Loading / error / empty states

Every panel handles loading (skeleton/pulse), empty
("No incidents recorded yet."), unavailable ("Backend unavailable.
Retrying…", "Policy retrieval unavailable.", "AI analysis unavailable.")
and error + retry. No placeholder data is ever presented as real.

## 9. Accessibility

Keyboard-accessible buttons/links, visible focus states, `role="status"`
+ `aria-label` on live regions and connection badges, severity as text
labels (never color-only), ENTER/EXIT as text badges.

## 10. Tests

Backend (`tests/test_events_stream.py`, 7 tests): bus pub/sub,
slow-consumer drop, SSE delivery over a real uvicorn server, heartbeat
keep-alive, worker→bus zone_enter (fake detector + ZoneConfig),
analyze→bus and reprocess→bus incident events.

Frontend (vitest + jsdom + testing-library, 11 tests):
`eventStream` singleton (one source, fan-out, dedup, state broadcast,
malformed-JSON guard), `LiveFeedPanel` (empty states, ENTER badge,
incident display, auto-analyze on enter only, per-event dedup,
connection badge).

Full backend regression: **175/175** (168 + 7). Frontend build green.

## 11. Known limitations

- The in-process bus does not survive multi-worker deployments
  (single uvicorn worker assumed — fine for this FYP target).
- SSE reconnect replays nothing; history covers gaps.
- Overview polls every 15 s (lightweight); live updates for incidents
  arrive via SSE.
- `npm install --legacy-peer-deps` needed: vitest 5 peer-resolves
  `@types/node` beyond the project's pinned v20 (dev-only, no runtime
  impact).
- No notifications, analytics, or multi-camera correlation (Phase 9+).
