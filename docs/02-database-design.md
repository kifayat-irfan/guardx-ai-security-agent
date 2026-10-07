# GuardX — Database Design (Phase 0)

PostgreSQL 16 is the system of truth. ChromaDB is a derived vector index
(rebuilt from `policies/`). High-volume per-frame detections are **not**
stored — only incidents, their snapshots, and the graph audit trail.

## ER diagram

```
cameras 1───* zones 1───* incidents 1───1 incident_reports
   │                    │ 1               │
   │                    │                 │
   │                    *───* incident_events (audit trail of graph steps)
   │                    │
   │                    *───* notifications
   │
   *───* (zones.polygon stored as JSONB; incidents reference camera+zone)
```

`policies` table mirrors `policies/*.md` files (title, category, version,
content) — the source that gets chunked into ChromaDB.

## Tables

### cameras
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| name | TEXT NOT NULL | e.g. "Gate Camera 1" |
| source_type | TEXT NOT NULL | `file` \| `rtsp` \| `webcam` |
| source_url | TEXT NOT NULL | path, RTSP URL, or device index |
| status | TEXT NOT NULL DEFAULT 'idle' | `idle` \| `streaming` \| `error` |
| created_at | TIMESTAMPTZ DEFAULT now() | |

### zones
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| camera_id | UUID FK → cameras.id | ON DELETE CASCADE |
| name | TEXT NOT NULL | e.g. "Server Room Door" |
| polygon | JSONB NOT NULL | `[[x,y],...]` normalized 0–1, ≥3 points |
| dwell_seconds | FLOAT DEFAULT 2.0 | must stay inside this long to fire |
| cooldown_seconds | FLOAT DEFAULT 60 | min gap before re-firing |
| active | BOOL DEFAULT true | |
| created_at | TIMESTAMPTZ DEFAULT now() | |

### incidents
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| camera_id | UUID FK → cameras.id | |
| zone_id | UUID FK → zones.id | |
| track_id | TEXT | vision tracker ID (may be null) |
| incident_type | TEXT NOT NULL | e.g. `restricted_area_intrusion` |
| status | TEXT NOT NULL DEFAULT 'open' | `open` \| `acknowledged` \| `resolved` \| `error` |
| severity | TEXT | set by graph: `low` \| `medium` \| `high` \| `critical` |
| detected_at | TIMESTAMPTZ NOT NULL | |
| snapshot_path | TEXT | annotated frame saved at detection |
| resolved_at | TIMESTAMPTZ | |

Index: `(status, detected_at DESC)`, `(zone_id, detected_at DESC)`.

### incident_events (graph audit trail)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| incident_id | UUID FK → incidents.id | ON DELETE CASCADE |
| step | TEXT NOT NULL | graph node name: `validate`, `retrieve_policies`, `reason`, `build_report`, `persist`, `notify` |
| payload | JSONB | node inputs/outputs (policies retrieved, decision, errors) |
| created_at | TIMESTAMPTZ DEFAULT now() | |

Powers the dashboard "Incident Timeline" — each LangGraph node writes one row.

### incident_reports
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| incident_id | UUID FK → incidents.id UNIQUE | one report per incident |
| severity | TEXT NOT NULL | |
| reason | TEXT NOT NULL | why this severity |
| matched_policy | TEXT NOT NULL | policy title + section cited |
| recommended_action | TEXT NOT NULL | |
| report_summary | TEXT NOT NULL | human-readable paragraph |
| model | TEXT | `provider/model` that produced it |
| created_at | TIMESTAMPTZ DEFAULT now() | |

### policies
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| title | TEXT NOT NULL | |
| category | TEXT NOT NULL | `restricted_area` \| `after_hours` \| `visitor` \| `emergency` \| `reporting` |
| version | TEXT NOT NULL DEFAULT '1.0' | |
| content | TEXT NOT NULL | full markdown source |
| updated_at | TIMESTAMPTZ DEFAULT now() | |

### notifications
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| incident_id | UUID FK → incidents.id | |
| channel | TEXT NOT NULL | `n8n_webhook` (MVP) |
| target | TEXT NOT NULL | webhook URL (redacted host in logs) |
| status | TEXT NOT NULL | `sent` \| `failed` \| `skipped` |
| detail | TEXT | error message if failed |
| sent_at | TIMESTAMPTZ DEFAULT now() | |

## Migrations

Alembic (`backend/alembic/`), one revision per phase that touches the schema:
- Phase 1: cameras, zones, policies
- Phase 7: incidents, incident_events, incident_reports, notifications
- `alembic upgrade head` runs automatically on backend startup (dev compose).
