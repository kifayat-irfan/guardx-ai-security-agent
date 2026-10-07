"""Phase 8: live event bus + SSE stream tests.

Note: starlette's TestClient and httpx's ASGITransport buffer the entire
response, so infinite SSE streams can only be tested against a real
server. These tests run uvicorn in a thread (same process, so the
in-process bus is shared).
"""
import socket
import threading
import time
import uuid

import httpx
import pytest
import uvicorn

from app.events.bus import EventBus, bus
from app.main import app


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture()
def live_server():
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port,
                       log_level="error")
    )
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    deadline = time.time() + 20
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started, "uvicorn did not start"
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    t.join(timeout=10)


def _stream_events(base_url, want_types, publish_fn=None, timeout=20):
    """Stream SSE until all want_types seen; optionally publish mid-stream."""
    seen = {}
    deadline = time.time() + timeout
    # trust_env=False: this VM's no_proxy contains bracketed IPv6 tokens
    # that break httpx proxy parsing (Phase 1 lesson).
    with httpx.Client(base_url=base_url, timeout=timeout + 5,
                      trust_env=False) as client:
        with client.stream("GET", "/api/v1/events/stream") as r:
            assert r.status_code == 200
            assert "text/event-stream" in r.headers["content-type"]
            if publish_fn:
                publish_fn()
            event_type = None
            for raw in r.iter_lines():
                if time.time() > deadline:
                    break
                if raw.startswith("event:"):
                    event_type = raw.split(":", 1)[1].strip()
                elif raw.startswith("data:") and event_type:
                    if event_type not in seen:
                        seen[event_type] = raw.split(":", 1)[1].strip()
                    if all(t in seen for t in want_types):
                        break
                    event_type = None
    return seen


# -- bus unit -----------------------------------------------------------------


def test_bus_pub_sub():
    b = EventBus()
    q = b.subscribe()
    assert b.subscriber_count() == 1
    b.publish("zone_event", {"a": 1})
    msg = q.get(timeout=2)
    assert msg == {"type": "zone_event", "data": {"a": 1}}
    b.unsubscribe(q)
    assert b.subscriber_count() == 0


def test_bus_slow_consumer_does_not_block():
    b = EventBus(maxsize=1)
    q = b.subscribe()
    b.publish("x", {"i": 0})
    b.publish("x", {"i": 1})  # queue full -> dropped, no block
    assert q.get(timeout=2)["data"] == {"i": 0}
    b.unsubscribe(q)


# -- SSE delivery over a real server -------------------------------------------


def test_sse_delivers_bus_events(live_server):
    def _pub():
        bus.publish("zone_event",
                    {"event_id": "e1", "zone_name": "server-room"})
        bus.publish("incident",
                    {"incident_id": "i1", "status": "completed"})

    seen = _stream_events(live_server, {"connected", "zone_event",
                                        "incident"},
                         publish_fn=_pub, timeout=15)
    assert "connected" in seen
    assert '"e1"' in seen["zone_event"]
    assert '"i1"' in seen["incident"]


def test_sse_heartbeat_keeps_alive(live_server):
    # stream stays open with no events (client would time out otherwise)
    seen = _stream_events(live_server, {"connected"}, timeout=8)
    assert "connected" in seen


# -- worker publishes zone events to the bus ------------------------------------


def test_worker_publishes_zone_events(tmp_path, monkeypatch):
    import cv2
    import numpy as np

    from app.vision.camera_worker import CameraWorker
    from app.vision.detector import Detection
    from app.zone_engine.zone import ZoneConfig

    class _InZoneDetector:
        last_inference_ms = 1.0

        def detect(self, image, frame_index=0, timestamp=None):
            return [Detection(bbox=[140.0, 180.0, 180.0, 230.0],
                              confidence=0.9)]

    # the worker reloads zones from the DB at startup; keep our test zones
    monkeypatch.setattr(CameraWorker, "reload_zones", lambda self, db=None: 1)

    path = tmp_path / "clip.mp4"
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (320, 240)
    )
    for _ in range(30):
        writer.write(np.zeros((240, 320, 3), dtype=np.uint8))
    writer.release()

    q = bus.subscribe()
    try:
        worker = CameraWorker(
            camera_id=uuid.uuid4(), source_type="file", source_url=str(path),
            detector=_InZoneDetector(), loop=False, frame_skip=1,
        )
        worker.zone_engine.set_zones([ZoneConfig(
            id=uuid.uuid4(), camera_id=worker.camera_id, name="server-room",
            polygon=[[0.3, 0.8], [0.7, 0.8], [0.7, 1.0], [0.3, 1.0]],
            dwell_seconds=0.05, cooldown_seconds=60.0,
        )])
        worker.start()
        deadline = time.time() + 20
        found = None
        while time.time() < deadline and found is None:
            try:
                msg = q.get(timeout=1)
            except Exception:
                continue
            if (msg["type"] == "zone_event"
                    and msg["data"].get("zone_name") == "server-room"):
                found = msg["data"]
        worker.stop()
        assert found is not None, "no zone_event published by worker"
        assert found["event_type"] == "zone_enter"
    finally:
        bus.unsubscribe(q)


# -- analyze endpoint publishes incident events -----------------------------------

from tests.test_incidents_db import api_client, pg_engine  # noqa: E402,F401
# (fixture reuse: api_client needs pg_engine in this module's namespace)


def test_analyze_publishes_incident_event(api_client, monkeypatch):
    client, _, _ = api_client
    published = []
    monkeypatch.setattr(
        bus, "publish",
        lambda et, data: published.append((et, data)),
    )
    from tests.test_incidents_workflow import make_event

    r = client.post("/api/v1/incidents/analyze",
                    json=make_event().model_dump(mode="json"))
    assert r.status_code == 200, r.text
    incident_id = r.json()["incident_id"]
    kinds = [et for et, _ in published]
    assert "incident" in kinds
    payload = next(d for et, d in published if et == "incident")
    assert payload["incident_id"] == incident_id
    assert payload["status"] == "completed"


def test_reprocess_publishes_incident_event(api_client, monkeypatch):
    client, _, _ = api_client
    published = []
    monkeypatch.setattr(
        bus, "publish",
        lambda et, data: published.append((et, data)),
    )
    from tests.test_incidents_workflow import make_event

    r = client.post("/api/v1/incidents/analyze",
                    json=make_event().model_dump(mode="json"))
    iid = r.json()["incident_id"]
    published.clear()
    r = client.post(f"/api/v1/incidents/{iid}/reprocess")
    assert r.status_code == 200, r.text
    payload = next(d for et, d in published if et == "incident")
    assert payload["incident_id"] == iid
    assert payload["reprocessed"] is True
