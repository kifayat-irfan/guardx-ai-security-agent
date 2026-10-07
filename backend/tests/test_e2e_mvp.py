"""Phase 10: deterministic end-to-end MVP verification.

One chain, no mocks of the pipeline itself (only the detector is
scripted — a real person video is unavailable on this box; the real
YOLO model load/inference is verified separately):

video -> worker -> zone_enter -> bus -> analyze -> LangGraph -> RAG
-> persist -> history -> detail -> reprocess (no duplicate)
-> n8n disabled (no webhook)
"""
import time
import uuid

import cv2
import numpy as np
import pytest

from app.events.bus import bus
from app.vision.camera_worker import CameraWorker
from app.vision.detector import Detection
from app.zone_engine.zone import ZoneConfig

from tests.test_incidents_db import api_client, pg_engine  # noqa: E402,F401
from tests.test_incidents_workflow import make_event  # noqa: E402


class _ScriptedPersonDetector:
    """Deterministic stand-in: one person standing in the zone."""

    last_inference_ms = 2.0

    def detect(self, image, frame_index=0, timestamp=None):
        return [Detection(bbox=[140.0, 180.0, 180.0, 230.0], confidence=0.9)]


def _make_clip(path, frames=30):
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (320, 240)
    )
    for _ in range(frames):
        writer.write(np.zeros((240, 320, 3), dtype=np.uint8))
    writer.release()


def test_e2e_mvp_person_enters_server_room(tmp_path, monkeypatch, api_client):
    client, _, _ = api_client
    monkeypatch.setattr(CameraWorker, "reload_zones", lambda self, db=None: 1)

    # 1-5. video -> worker -> zone_enter on the bus
    _make_clip(tmp_path / "e2e.mp4")
    q = bus.subscribe()
    try:
        worker = CameraWorker(
            camera_id=uuid.uuid4(), source_type="file",
            source_url=str(tmp_path / "e2e.mp4"),
            detector=_ScriptedPersonDetector(), loop=False, frame_skip=1,
        )
        worker.zone_engine.set_zones([ZoneConfig(
            id=uuid.uuid4(), camera_id=worker.camera_id, name="server-room",
            polygon=[[0.3, 0.8], [0.7, 0.8], [0.7, 1.0], [0.3, 1.0]],
            dwell_seconds=0.05, cooldown_seconds=60.0,
        )])
        worker.start()
        zone_event = None
        deadline = time.time() + 20
        while time.time() < deadline and zone_event is None:
            try:
                msg = q.get(timeout=1)
            except Exception:
                continue
            if msg["type"] == "zone_event":
                zone_event = msg["data"]
        worker.stop()
    finally:
        bus.unsubscribe(q)
    assert zone_event is not None, "pipeline produced no zone event"
    assert zone_event["event_type"] == "zone_enter"
    assert zone_event["zone_name"] == "server-room"

    # 6-12. analyze -> LangGraph -> RAG -> persist (fake LLM -> completed)
    r = client.post("/api/v1/incidents/analyze", json=zone_event)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["severity"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert body["cited_policy_chunk_ids"], "no policy citations"
    iid = body["incident_id"]

    # 13. report persisted on success
    r = client.get(f"/api/v1/incidents/{iid}/report")
    assert r.status_code == 200
    assert r.json()["incident_id"] == iid

    # 14-15. history + detail carry event/policy/workflow info
    r = client.get("/api/v1/incidents?page=1&page_size=5")
    assert r.status_code == 200
    assert any(i["id"] == iid for i in r.json()["items"])

    r = client.get(f"/api/v1/incidents/{iid}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["incident"]["zone_name"] == "server-room"
    assert detail["incident"]["event_data"]["zone_name"] == "server-room"
    assert detail["report"]["cited_policy_chunk_ids"] == \
        body["cited_policy_chunk_ids"]

    # 16. reprocess: same id, no duplicate
    r = client.post(f"/api/v1/incidents/{iid}/reprocess")
    assert r.status_code == 200
    assert r.json()["incident_id"] == iid
    r = client.get("/api/v1/incidents?page=1&page_size=100")
    ids = [i["id"] for i in r.json()["items"]]
    assert ids.count(iid) == 1

    # 17. n8n disabled by default -> incident path unaffected (no webhook
    # config in this environment; the disabled no-op is unit-tested)
    from app.automation.service import get_automation_service

    assert get_automation_service().enabled is False
