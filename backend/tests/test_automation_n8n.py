"""Phase 9: n8n automation + incident notification tests.

All HTTP is mocked — no real n8n server required.
"""
import json
import logging
import threading
import uuid
from datetime import datetime, timezone

import httpx
import pytest

from app.automation.n8n import SECRET_HEADER, N8nClient
from app.automation.schemas import N8nIncidentPayload
from app.automation.service import AutomationService, get_automation_service


def _client(handler=None, **kw):
    transport = httpx.MockTransport(handler) if handler else None
    secret = kw.pop("secret", "s3cr3t")
    return N8nClient(webhook_url="http://n8n:5678/webhook/guardx-incident",
                     secret=secret, timeout_seconds=2.0,
                     transport=transport, **kw)


def _svc(client, enabled=True):
    svc = AutomationService(client=client)
    svc.enabled = enabled
    return svc


def _payload(**kw):
    base = dict(
        event_id=str(uuid.uuid4()),
        event_type="incident",
        occurred_at=datetime.now(timezone.utc),
        camera_id=str(uuid.uuid4()),
        zone_id=str(uuid.uuid4()),
        zone_name="server-room",
        source_event_type="zone_enter",
        track_id=3,
        detection_confidence=0.9,
        incident_id=str(uuid.uuid4()),
        workflow_id="wf-1",
        status="completed",
        severity="HIGH",
        summary="A person entered the server room.",
        analysis="Policy SEC-001 requires escorting visitors.",
        cited_policy_chunk_ids=["SEC-001#visitor-access"],
        retrieved_policy_count=3,
        reprocessed=False,
    )
    base.update(kw)
    return N8nIncidentPayload(**base)


# 1. disabled -> no HTTP, core op unaffected ------------------------------------


def test_disabled_sends_nothing():
    calls = []

    def _handler(request):
        calls.append(request)
        return httpx.Response(200, json={"ok": True})

    svc = _svc(_client(_handler), enabled=False)
    assert svc.notify_incident_sync(_FakeIncident(), _FakeDecision()) \
        .status == "disabled"
    assert svc._dispatch(_payload()) is None
    assert calls == []


# 2. enabled + successful webhook --------------------------------------------------


def test_successful_webhook():
    seen = {}

    def _handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content.decode())
        seen["secret"] = request.headers.get(SECRET_HEADER)
        return httpx.Response(200, json={"ok": True})

    svc = _svc(_client(_handler))
    result = svc.notify_incident_sync(_FakeIncident(), _FakeDecision())
    assert result.status == "sent"
    assert seen["url"] == "http://n8n:5678/webhook/guardx-incident"
    assert seen["secret"] == "s3cr3t"
    assert seen["body"]["event_type"] == "incident"
    assert seen["body"]["severity"] == "HIGH"


# 3/4/5. timeout, connection failure, HTTP 5xx ----------------------------------------


def _raiser(exc):
    def _handler(request):
        raise exc

    return _handler


@pytest.mark.parametrize("exc", [
    httpx.TimeoutException("slow"),
    httpx.ConnectError("refused"),
])
def test_network_failures_are_contained(exc):
    svc = _svc(_client(_raiser(exc)))
    result = svc.notify_incident_sync(_FakeIncident(), _FakeDecision())
    assert result.status == "failed"
    assert result.detail in ("timeout", "unreachable")


def test_http_500_is_contained():
    svc = _svc(_client(lambda r: httpx.Response(500, json={"e": 1})))
    result = svc.notify_incident_sync(_FakeIncident(), _FakeDecision())
    assert result.status == "failed"
    assert result.detail == "HTTP 500"


def test_not_configured_without_url():
    svc = _svc(N8nClient(webhook_url="", secret="s3cr3t"))
    result = svc.notify_incident_sync(_FakeIncident(), _FakeDecision())
    assert result.status == "not_configured"


# 6. payload serialization -------------------------------------------------------------


def test_payload_is_json_serializable():
    p = _payload()
    raw = p.model_dump(mode="json")
    text = json.dumps(raw)  # must not raise
    back = json.loads(text)
    assert back["incident_id"] == p.incident_id
    assert back["cited_policy_chunk_ids"] == ["SEC-001#visitor-access"]
    assert back["reprocessed"] is False


# 7. secret header handling ----------------------------------------------------------------


def test_secret_header_only_when_configured():
    seen = {}

    def _handler(request):
        seen["secret"] = request.headers.get(SECRET_HEADER)
        return httpx.Response(200, json={})

    _client(_handler, secret="").send(_payload())
    assert seen["secret"] is None

    _client(_handler, secret="abc").send(_payload())
    assert seen["secret"] == "abc"


# 8. secret is never logged ---------------------------------------------------------------------


def test_secret_not_logged(caplog):
    svc = _svc(_client(lambda r: httpx.Response(500, json={})))
    with caplog.at_level(logging.WARNING, logger="app.automation.n8n"):
        svc.notify_incident_sync(_FakeIncident(), _FakeDecision())
    assert "s3cr3t" not in caplog.text


# 9/10. severity + status preserved ---------------------------------------------------------------


def test_severity_preserved_verbatim():
    svc = AutomationService(client=_client(lambda r: httpx.Response(200)))
    svc.enabled = True
    for sev in ("LOW", "MEDIUM", "HIGH", "CRITICAL", None):
        p = svc.build_incident_payload(
            _FakeIncident(), _FakeDecision(severity=sev))
        assert p.severity == sev, sev


def test_llm_unavailable_keeps_honest_status():
    svc = AutomationService(client=_client(lambda r: httpx.Response(200)))
    svc.enabled = True
    p = svc.build_incident_payload(
        _FakeIncident(),
        _FakeDecision(status="llm_unavailable", severity=None),
    )
    assert p.status == "llm_unavailable"
    assert p.severity is None


# 12/13. zone + incident events trigger ------------------------------------------------------------


def test_zone_enter_builds_payload():
    svc = AutomationService(client=_client(lambda r: httpx.Response(200)))
    svc.enabled = True
    p = svc.build_zone_payload(_FakeZoneEvent())
    assert p.event_type == "zone_event"
    assert p.source_event_type == "zone_enter"
    assert p.zone_name == "server-room"
    assert p.severity is None  # no AI yet — honest


def test_notify_dispatches_in_background():
    seen = []

    def _handler(request):
        seen.append(json.loads(request.content.decode()))
        return httpx.Response(200, json={})

    svc = _svc(_client(_handler))
    t = svc.notify_incident(_FakeIncident(), _FakeDecision())
    assert isinstance(t, threading.Thread)
    t.join(timeout=10)
    assert len(seen) == 1
    assert seen[0]["event_type"] == "incident"


def test_notify_zone_event_dispatches():
    seen = []

    def _handler(request):
        seen.append(json.loads(request.content.decode()))
        return httpx.Response(200, json={})

    svc = _svc(_client(_handler))
    t = svc.notify_zone_event(_FakeZoneEvent())
    assert isinstance(t, threading.Thread)
    t.join(timeout=10)
    assert seen[0]["event_type"] == "zone_event"


# 15. reprocessed flag --------------------------------------------------------------------------------


def test_reprocessed_flag_in_payload():
    svc = AutomationService(client=_client(lambda r: httpx.Response(200)))
    svc.enabled = True
    p = svc.build_incident_payload(
        _FakeIncident(), _FakeDecision(), reprocessed=True)
    assert p.reprocessed is True


# 14. health states --------------------------------------------------------------------------------------


def test_health_disabled():
    svc = _svc(_client(), enabled=False)
    state, _ = svc.health_status()
    assert state == "disabled"


def test_health_configured_without_url():
    svc = AutomationService(client=N8nClient(webhook_url=""))
    svc.enabled = True
    state, _ = svc.health_status()
    assert state == "configured"


def test_health_unreachable():
    # nothing listens on this port
    svc = _svc(N8nClient(webhook_url="http://127.0.0.1:9/webhook/x"))
    state, detail = svc.health_status()
    assert state == "unreachable"
    assert "s3cr3t" not in (detail or "")


def test_health_reachable():
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(404)
            self.end_headers()

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), _H)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        svc = _svc(N8nClient(
            webhook_url=f"http://127.0.0.1:{port}/webhook/x"))
        state, _ = svc.health_status()
        assert state == "reachable"
    finally:
        server.shutdown()


def test_public_status_has_no_secrets():
    svc = _svc(_client())
    st = svc.public_status()
    assert st == {"enabled": True, "configured": True,
                  "reachable": False, "provider": "n8n"}
    assert "s3cr3t" not in json.dumps(st)


# 11. automation failure does not break persistence -------------------------------------------


from tests.test_incidents_db import api_client, pg_engine  # noqa: E402,F401
from app.main import app  # noqa: E402


def test_automation_failure_does_not_rollback_incident(api_client, pg_engine):
    from sqlalchemy import text

    from tests.test_incidents_workflow import make_event

    client, _, _ = api_client
    engine = pg_engine

    def _boom(request):
        raise httpx.ConnectError("n8n is down")

    svc = AutomationService(
        client=N8nClient(webhook_url="http://n8n:5678/webhook/x",
                         transport=httpx.MockTransport(_boom)))
    svc.enabled = True
    app.dependency_overrides[get_automation_service] = lambda: svc
    try:
        r = client.post("/api/v1/incidents/analyze",
                        json=make_event().model_dump(mode="json"))
        assert r.status_code == 200, r.text
        iid = r.json()["incident_id"]
        with engine.begin() as conn:
            n = conn.execute(
                text("SELECT COUNT(*) FROM incidents WHERE id=:i"),
                {"i": iid},
            ).scalar()
        assert n == 1  # persisted despite the dead webhook
    finally:
        app.dependency_overrides.pop(get_automation_service, None)


def test_automation_status_endpoint(api_client):
    client, _, _ = api_client
    svc = AutomationService(client=N8nClient(webhook_url=""))
    svc.enabled = False
    app.dependency_overrides[get_automation_service] = lambda: svc
    try:
        r = client.get("/api/v1/automation/status")
        assert r.status_code == 200
        body = r.json()
        assert body["provider"] == "n8n"
        assert body["enabled"] is False
        assert "secret" not in json.dumps(body).lower()
    finally:
        app.dependency_overrides.pop(get_automation_service, None)


# -- fakes -------------------------------------------------------------------------------------------


class _FakeDecision:
    def __init__(self, status="completed", severity="HIGH"):
        self.workflow_id = "wf-1"
        self.status = status
        self.severity = severity
        self.summary = "summary"
        self.reasoning = "reasoning"
        self.cited_policy_chunk_ids = ["SEC-001#x"]
        self.retrieved_policy_count = 2


class _FakeIncident:
    id = uuid.uuid4()
    occurred_at = datetime.now(timezone.utc)
    camera_id = uuid.uuid4()
    zone_id = uuid.uuid4()
    zone_name = "server-room"
    event_type = "zone_enter"
    tracking_id = 3
    detection_confidence = 0.9


class _FakeZoneEvent:
    event_id = uuid.uuid4()
    camera_id = uuid.uuid4()
    zone_id = uuid.uuid4()
    zone_name = "server-room"
    event_type = "zone_enter"
    tracking_id = 3
    confidence = 0.9
