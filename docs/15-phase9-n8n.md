# Phase 9 — n8n Automation & Incident Notifications

**Status: complete and verified (2026-10-07).**

> n8n is an **optional** external automation layer. GuardX works fully
> without it. Notification failure never breaks incident persistence.

## 1. Architecture

```
zone event ──► camera worker ──► event bus (SSE) ──┐
                                                  ▼
incident ──► LangGraph ──► PostgreSQL ──► incidents API
                                                  │
                              ┌───────────────────┘
                              ▼ (fire-and-forget, daemon thread)
                     AutomationService
                              │  POST JSON + X-GuardX-Webhook-Secret
                              ▼
                       n8n webhook (/webhook/guardx-incident)
                              │  validate → normalize → branch
                              ▼
                    urgent / standard placeholder actions
```

Nothing before Phase 9 was replaced: the event bus, SSE stream,
workflow, and persistence are untouched. Automation hooks in *after*
persistence.

## 2. Configuration (env vars)

| Variable | Default | Meaning |
|---|---|---|
| `N8N_ENABLED` | `false` | master switch — default **disabled** |
| `N8N_WEBHOOK_URL` | `""` | n8n webhook URL (e.g. `http://n8n:5678/webhook/guardx-incident`) |
| `N8N_WEBHOOK_SECRET` | `""` | shared secret, sent as `X-GuardX-Webhook-Secret` |
| `N8N_WEBHOOK_TIMEOUT_SECONDS` | `5.0` | POST timeout (short, non-blocking) |

Conventions follow `app/core/config.py` (pydantic-settings, `../.env`
fallback). docker-compose passes these through to the backend service;
the `n8n` service stays profile-gated
(`docker compose --profile automation up`).

## 3. Payload schema

`app/automation/schemas.py::N8nIncidentPayload` — stable, JSON
serializable, secret-free:

`source, event_id, event_type (zone_event|incident), occurred_at,
camera_id, zone_id, zone_name, source_event_type, track_id,
detection_confidence, incident_id, workflow_id, status, severity,
summary, analysis, cited_policy_chunk_ids, retrieved_policy_count,
reprocessed`.

**Honesty rule:** `status`/`severity` are copied verbatim from the
validated workflow. An `llm_unavailable` incident keeps
`status="llm_unavailable"` and `severity=None` — nothing is invented.

## 4. Authentication

When `N8N_WEBHOOK_SECRET` is set, every webhook POST carries
`X-GuardX-Webhook-Secret`. The secret comes only from the environment,
is never logged, and never appears in `/automation/status` or health.
The bundled n8n workflow optionally enforces it via the
`GUARDX_WEBHOOK_SECRET` n8n env var (skipped when empty).

## 5. Failure isolation

- Disabled / unconfigured → no network traffic at all.
- Enabled → delivery runs in a **daemon thread after the DB commit**;
  the API never waits on n8n.
- Timeout, DNS/connection failure, HTTP 4xx/5xx, malformed responses →
  logged (without the secret) and swallowed. The incident is already
  persisted; the API still returns 200.
- All automation code paths are wrapped so exceptions cannot reach the
  incident transaction.

## 6. Health states

`GET /api/v1/health/detailed` → `n8n` component:

- `disabled` — `N8N_ENABLED=false`
- `configured` — enabled but no webhook URL
- `reachable` — enabled + URL + light GET probe succeeded
- `unreachable` — enabled + URL + probe failed
- `error` — probe raised

"Healthy" is never claimed from config alone. The dashboard
`HealthPanel` renders this verbatim (Phase 8 placeholder replaced).

`GET /api/v1/automation/status` → safe subset:
`{enabled, configured, reachable, provider: "n8n"}` — no secrets.

## 7. n8n workflow

`n8n/workflows/guardx-incident-alert.json`:

Webhook (`POST /guardx-incident`) → **Normalize** (Code: secret check,
field normalization, `urgent` flag, alert title) → **Urgent?** (IF on
`urgent`) → **Urgent Alert** / **Standard Alert** (Set nodes — safe
credential-free placeholders; wire real pager/email/chat credentials
here) → **Respond** (200 to GuardX).

Branching: `HIGH`/`CRITICAL` → urgent; everything else (including
`llm_unavailable` with no severity) → standard.

Import: n8n UI → Workflows → Import from file → select the JSON →
activate. Set `GUARDX_WEBHOOK_SECRET` in the n8n environment to match
GuardX's `N8N_WEBHOOK_SECRET`.

## 8. Testing (22 tests, `tests/test_automation_n8n.py`)

Disabled (no HTTP, no-op) · success (200, URL/secret/payload asserted) ·
timeout · connection failure · HTTP 500 · not-configured · JSON
serialization · secret header present/absent · secret never logged ·
severity verbatim (LOW/MEDIUM/HIGH/CRITICAL/None) · `llm_unavailable`
kept honest · zone payload (`severity=None`) · background dispatch ·
reprocessed flag · health disabled/configured/unreachable/reachable
(local test server) · public status secret-free · **webhook-down API
test: analyze → 200 + incident persisted** · status endpoint.

All HTTP mocked; no real n8n needed. Full backend: **197/197**.

## 9. Demo (verified live)

1. Mock webhook server on :5999; backend with `N8N_ENABLED=true`.
2. `/automation/status` → `enabled/configured/reachable: true`;
   health `n8n: reachable`.
3. `POST /incidents/analyze` (zone_enter) → 200, incident persisted.
4. Webhook received: correct secret header, full payload,
   `status=llm_unavailable`, `severity=null`, `retrieved_policy_count=3`.
5. Mock server killed → health `n8n: unreachable`; analyze still 200,
   incident still persisted (failure isolation proven live).

Demo incidents cleaned from the dev DB afterwards.

## 10. Known limitations

- Webhook delivery is at-most-once, fire-and-forget; no retry queue
  (documented Phase 10+ candidate, not implemented).
- Reachability probe is a light GET (webhooks expect POST; a 404/405
  handshake still proves reachability).
- The bundled workflow's notification nodes are placeholders — wire
  real credentials in n8n for production delivery.
- No retry/backoff, no per-severity routing config in GuardX itself
  (branching lives in the n8n workflow, as designed).
