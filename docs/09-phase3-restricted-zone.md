# Phase 3 — Restricted-Zone Engine

**Status: complete and verified (2026-10-07).**
Phase 2's pipeline (camera → YOLO → tracker) now feeds a deterministic
restricted-zone engine that emits structured `zone_enter` / `zone_exit`
events. No RAG, LangChain, LangGraph, incidents, or n8n in this phase.

## 1. Zone coordinate format

Zones are stored in the `zones` table (PostgreSQL, source of truth) as
`polygon` JSONB: a canonical list of `[x, y]` pairs, **normalized 0.0–1.0**
relative to the frame:

- `x = 0` is the left edge, `x = 1` the right edge.
- `y = 0` is the top edge, `y = 1` the bottom edge (image coordinates).
- Minimum 3 points; every coordinate must satisfy `0.0 <= v <= 1.0`
  (validated at the API boundary, 422 on violation).

The API accepts two input shapes and normalizes both to the canonical form:

```json
[[0.10, 0.20], [0.80, 0.20], [0.80, 0.80], [0.10, 0.80]]
[{"x": 0.10, "y": 0.20}, {"x": 0.80, "y": 0.20}, ...]
```

## 2. Polygon logic

`backend/app/zone_engine/geometry.py`

- `point_in_polygon(point, polygon)` — pure-Python ray casting, deterministic,
  no OpenCV dependency. **Points exactly on an edge count as inside.**
- `bottom_center(bbox)` — reference point of a detection.

## 3. Bottom-center point logic

Each person's reference point is the **bottom-center of the YOLO bbox**:
`((x1+x2)/2, y2)`, approximating the person's feet on the ground. The point
is converted to normalized 0–1 coordinates (divided by frame width/height)
before the polygon test, so zones are resolution-independent.

## 4. Entry/exit state machine

`backend/app/zone_engine/engine.py` — `ZoneEngine`

State is tracked per **(camera_id, zone_id, track_id)**:

```
OUTSIDE --(point inside)--> PENDING --(dwell met)--> INSIDE (zone_enter fired)
   ^                           |                          |
   |----(point outside)---------+----(point outside)-------+
              (no event)              (zone_exit fired)
```

- `OUTSIDE → INSIDE` (via dwell): emits `zone_enter` — exactly once.
- `INSIDE → INSIDE`: no repeated events (duplicate-enter suppression).
- `INSIDE → OUTSIDE`: emits `zone_exit`.
- `PENDING → OUTSIDE` (left before dwell elapsed): no event — flicker killer.
- A track that vanishes while `INSIDE`/`PENDING` emits `zone_exit` with
  `metadata.reason = "track_expired"` after `max_missed` frames (default 10),
  carrying the last known point/bbox/confidence.
- Disabled zones are never loaded into the engine (`set_zones` filters them).

All timestamps are frame-time seconds (float). Same input sequence →
same event sequence: fully deterministic.

## 5. Dwell behavior

`dwell_seconds` (default 2.0, configurable per zone): a person must be
**continuously inside** for this long before `zone_enter` fires. Brief
pass-throughs and edge flicker never produce events. The elapsed dwell is
recorded in `event.metadata.dwell_elapsed`.

## 6. Cooldown behavior

`cooldown_seconds` (default 60.0, configurable per zone): after a `zone_enter`
fires for a (zone, track) pair, no new `zone_enter` fires for that pair until
the cooldown elapses — even if the person leaves and re-enters. Prevents
event spam from loitering at a boundary.

## 7. API endpoints

All under `/api/v1/zones` (`backend/app/api/v1/routers/zones.py`):

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/zones` | Create zone (`camera_id`, `name`, `polygon`, `dwell_seconds`, `cooldown_seconds`, `active`) |
| GET | `/api/v1/zones?camera_id=&active=` | List zones (optional filters) |
| GET | `/api/v1/zones/{id}` | Get one zone |
| PATCH | `/api/v1/zones/{id}` | Update zone (incl. enable/disable) |
| DELETE | `/api/v1/zones/{id}` | Delete zone |

Validation: ≥3 polygon points, normalized coordinates, camera must exist.
After any create/update/delete, a running camera worker for that camera
automatically reloads its zones (`worker.reload_zones()`).

Migration `20261007_0002` added `updated_at` to the `zones` table.

## 8. Event schema

`backend/app/zone_engine/events.py` — `ZoneEvent` (Pydantic, strongly typed):

```
event_id, camera_id, zone_id, zone_name, tracking_id,
event_type: zone_enter | zone_exit,
timestamp, confidence, bounding_box (normalized xyxy),
point (normalized [x, y] bottom-center),
metadata (dwell_elapsed / inside_duration, reason, zone config snapshot)
```

This is the engine's **only** output. It does not create security incidents.

## 9. Camera integration

`backend/app/vision/camera_worker.py`:

```
frame → YOLO detect → centroid tracker → ZoneEngine.update → sweep
      → draw zone polygons on MJPEG → latest JPEG
```

- Worker loads the camera's **active** zones on start.
- Zone polygons are drawn on the MJPEG stream (red overlay + label).
- `/api/v1/cameras/{id}/status` now also returns `active_zones`,
  `active_track_ids`, `zone_events` (last 10), `track_states`.
- Existing lifecycle (start/stop/stream) unchanged; all Phase 2 tests still pass.

## 10. Dashboard

`frontend/components/ZonePanel.tsx` (wired into `CameraPanel`):

- Zone list with enable/disable toggle, edit, delete.
- Create/edit form: name, polygon JSON, dwell, cooldown.
- Live event feed with ENTER (red) / EXIT (green) badges, plus a banner
  alert when the latest event is a zone entry.
- Shows active tracking IDs; polygons are visible on the live stream
  (drawn server-side on the MJPEG frames).
- Dark GuardX HUD style preserved.

## 11. Tests

65 tests, all passing (35 from Phases 1–2 + 30 new):

- `tests/test_geometry.py` (9): inside/outside/boundary/on-edge,
  concave polygon, bottom-center, polygon validation (array + object forms,
  too-few-points, denormalized coords rejected).
- `tests/test_zone_engine.py` (13): enter on OUTSIDE→INSIDE, no repeated
  enter, exit on INSIDE→OUTSIDE, dwell flicker suppression, dwell firing,
  cooldown suppression/expiry, multiple tracking IDs, multiple zones,
  multiple cameras, disabled zone ignored, vanished-track exit, event schema.
- `tests/test_zones_api.py` (7): CRUD, filters, both polygon forms,
  validation rejections (short polygon, denormalized, unknown camera, bad update).
- `tests/test_zone_integration.py` (1): real YOLOv8n + tracker + engine on
  the Phase 2 test clip — asserts ≥1 enter, ≥1 exit, ≥2 tracks, both zones
  fired, no duplicate enters.

Deterministic synthetic detections (100×100 frame) for unit tests; no
external dataset.

## 12. Real-video verification

`scripts/verify_zone_events.py` — real run on
`assets/test_videos/person_pan_test.mp4` (looped, 150 frames), YOLOv8n +
centroid tracker + ZoneEngine, zones `middle-band` [0.35–0.65] and
`left-band` [0.02–0.28], dwell 0.3 s:

```
frames processed : 150 in 19.9s wall
total events     : 11
zone_enter       : 6
zone_exit        : 5
distinct tracks  : 4
zones fired      : ['left-band', 'middle-band']
duplicate enters : 0
VERIFICATION: PASS
```

Sample: `middle-band zone_enter track=2 t=4.88s point=[0.4464, 0.9996]
conf=0.60` → later `middle-band zone_exit track=2 t=7.32s
point=[0.3449, 0.9995]`. Entry point inside the polygon, exit point outside —
exactly as the pan carries people across the bands.

## 13. Known limitations

- Zones apply to one camera each; no zone templates shared across cameras.
- Zone editor is JSON-based (no drag-to-draw canvas yet).
- Dwell uses frame timestamps; a paused/stalled source delays firing.
- Cooldown is per (zone, track) — a *new* track ID for the same person
  (tracker ID switch) starts a fresh cooldown window.
- `zone_events` in the status endpoint keeps only the last 50 in memory
  (not persisted); Phase 6+ will persist incidents in Postgres.

## 14. How Phase 4 will consume zone events

- `ZoneEvent` is the contract: Phase 4's RAG retriever takes a
  `zone_enter` event (zone name, camera, timestamp, track) and fetches
  the relevant security policies from ChromaDB.
- `track_states()` exposes live dwell state (`inside_since`, `pending`)
  so the incident workflow can reason about loitering duration.
- The engine stays decision-free: it reports *where/when/who*, never
  *how severe* or *what to do* — those belong to the LangGraph workflow.
