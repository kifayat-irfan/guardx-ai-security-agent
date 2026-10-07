# Phase 7 — Incident Persistence and Reporting

**Status: complete and verified (2026-10-07).**

> **PostgreSQL is now the source of truth for incidents and reports.**
> ChromaDB remains the derived policy index. No notifications — later phases.

## 1. Architecture

```
zone event → LangGraph → validated decision → PostgreSQL
                                                ├─ incidents
                                                └─ incident_reports (FK, 1:1)
```

The LangGraph nodes are unchanged (Phase 6). Persistence happens in the
API layer after the workflow finishes: `IncidentWorkflowService` produces
the `IncidentDecision`, `IncidentRepository` writes it atomically.

## 2. Database schema

**incidents** — one row per analyzed zone event (including failures):

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| external_event_id | varchar(64), indexed | original ZoneEvent id |
| camera_id / zone_id | UUID, indexed | kept as values (no FK — history survives deletes) |
| zone_name | varchar(200), indexed | |
| tracking_id | integer | |
| event_type | varchar(32), indexed | zone_enter / zone_exit |
| occurred_at | timestamptz, indexed, default now() | wall-clock processing time |
| detection_confidence | float | |
| bounding_box / point | JSON | normalized coords |
| event_data | JSON | full original event — exact reconstruction |
| status | varchar(32), indexed | completed / invalid_event / retrieval_failed / no_policies / llm_unavailable / analysis_failed / citation_invalid |
| severity | varchar(16), indexed, nullable | LOW/MEDIUM/HIGH/CRITICAL (null on failure) |
| summary / recommended_action | text, nullable | |
| analysis_confidence | float, nullable | |
| error | JSON, nullable | {node, code, message} |
| workflow_id | varchar(64), unique, indexed | |
| created_at / updated_at | timestamptz | |

**incident_reports** — one report per incident (`incident_id` unique,
FK CASCADE):

report_type (default `ai_analysis`), title (`"Zone Entry — server-room"`),
summary, severity, recommended_action, reasoning, cited_policy_chunk_ids
(JSON), retrieved_policy_count, retrieved_chunk_ids (JSON), generated_at.

## 3. Migration

`alembic/versions/20261007_0003_incidents.py` (revises `20261007_0002`).
Verified: upgrade → downgrade → re-upgrade on the dev database, all clean.

## 4. Incident lifecycle

1. `POST /api/v1/incidents/analyze` receives a zone event.
2. LangGraph runs (Phase 6, unchanged).
3. `IncidentRepository.persist_workflow_result()` writes the incident in
   one transaction; on `completed` it also writes the report. Failure
   throws → rollback → HTTP 500 ("incident not saved") — never a
   half-created row, never a false success claim.
4. Failed workflows are persisted as failure-status incidents **without**
   a report, so failures stay observable; the structured failure decision
   is returned (with its `incident_id`).
5. `POST /api/v1/incidents/{id}/reprocess` reloads `event_data`, re-runs
   the graph, updates the incident **in place**, deletes and recreates
   the report — the incident id never changes, no duplicates.

## 5. Report generation

Reports are built only from the validated decision + stored event:
title from event type/zone, summary/severity/action copied verbatim,
reasoning from the validated analysis, citations copied verbatim. The
persistence layer never invents citations — the Phase 6 citation guard
(`cited ⊆ retrieved`) already passed before anything is written.

## 6. API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/incidents/analyze` | run workflow, persist, return decision + `incident_id` |
| GET | `/api/v1/incidents?page=&page_size=&status=&severity=&camera_id=&zone_name=` | history, newest first, paginated |
| GET | `/api/v1/incidents/{id}` | incident + report + event reconstruction |
| GET | `/api/v1/incidents/{id}/report` | the generated report |
| POST | `/api/v1/incidents/{id}/reprocess` | re-analyze stored event, update in place |
| GET | `/api/v1/incidents/workflows/{id}` | Phase 6 in-memory workflow inspection (unchanged) |

Pagination: `page ≥ 1`, `1 ≤ page_size ≤ 100`, response carries
`items/page/page_size/total/total_pages`.

## 7. Dashboard

New **Incident History** panel: incident count, filterable table
(status/severity/zone), severity/status badges, pagination, click-to-open
detail (event, AI summary, action, reasoning, cited vs retrieved chunk
IDs, workflow id, report time), and a **Reprocess** button — enabling the
FYP demo flow: policy edit → reindex → reprocess → updated report.

## 8. Health

`GET /api/v1/health/detailed` gains `postgres_incidents`:
`up`/`down`, incident count, and alembic revision vs latest
(`20261007_0003 (current)`). Never fails the backend.

## 9. Tests (14 new, dedicated `guardx_test` database)

Models (incident/report round-trip, relationship) · migration
upgrade/downgrade/re-upgrade via the real alembic CLI · failed workflow
stored without report · transaction rollback (report failure → zero rows)
· API analyze → incident + report persisted · failure not falsely
completed · pagination (page math, newest-first) · status/severity/
camera/zone filters · get incident/report + 404s · reprocess updates in
place (same id, one report) · citation preservation (verbatim, ⊆
retrieved) · policy edit → reindex → reprocess flow · health component.
Full suite: **168/168** (154 Phase 1–6 + 14 Phase 7).

## 10. Known limitations

- No notifications (Phase 8+); no analytics; single-camera events only.
- `occurred_at` is processing wall-clock time; the source-relative frame
  timestamp is preserved inside `event_data`.
- The in-memory Phase 6 workflow registry is still separate (bounded,
  non-persistent); the incident row is the durable record.
- Reprocess uses current policies — intended (that's the demo), but it
  means reprocessing after a policy change changes the outcome.
- During development, a programmatic-alembic test accidentally dropped
  the dev incident tables; repaired via stamp+upgrade and verified.
  The migration test now shells out to the real alembic CLI against the
  test database only.
