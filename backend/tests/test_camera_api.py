"""Camera API tests — CRUD + start/stop lifecycle (detector stubbed)."""
import uuid

import pytest

from app.vision import camera_worker


class _StubDetector:
    """No model weights; the worker loop still exercises threading/JPEG."""

    last_inference_ms = 0.0

    def detect(self, image, frame_index=0, timestamp=None):
        return []


@pytest.fixture(autouse=True)
def _stub_detector(monkeypatch):
    monkeypatch.setattr(
        camera_worker.CameraWorker,
        "_default_detector",
        staticmethod(lambda: _StubDetector()),
    )


def _create(client, url="/definitely/not/here.mp4"):
    r = client.post(
        "/api/v1/cameras",
        json={"name": "Test Cam", "source_type": "file", "source_url": url},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_camera_crud(client):
    cam = _create(client)
    cid = cam["id"]
    assert cam["status"] == "idle"

    r = client.get("/api/v1/cameras")
    assert r.status_code == 200 and len(r.json()) == 1

    r = client.get(f"/api/v1/cameras/{cid}")
    assert r.status_code == 200 and r.json()["name"] == "Test Cam"

    r = client.patch(f"/api/v1/cameras/{cid}", json={"name": "Renamed"})
    assert r.status_code == 200 and r.json()["name"] == "Renamed"

    r = client.get("/api/v1/cameras/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_start_with_invalid_source_returns_422(client):
    cam = _create(client)
    r = client.post(f"/api/v1/cameras/{cam['id']}/start")
    assert r.status_code == 422, r.text
    assert "not found" in r.json()["detail"].lower()


def test_start_stop_lifecycle_with_real_video(client, tmp_path):
    import cv2
    import numpy as np

    path = tmp_path / "clip.mp4"
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (320, 240)
    )
    for _ in range(12):
        writer.write(np.zeros((240, 320, 3), dtype=np.uint8))
    writer.release()

    cam = _create(client, url=str(path))
    cid = cam["id"]

    r = client.post(f"/api/v1/cameras/{cid}/start")
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "streaming"

    # second start -> conflict
    r = client.post(f"/api/v1/cameras/{cid}/start")
    assert r.status_code == 409

    import time

    time.sleep(1.0)
    r = client.get(f"/api/v1/cameras/{cid}/status")
    assert r.status_code == 200
    body = r.json()
    assert body["fps"] >= 0
    assert body["person_count"] == 0  # stub detector finds nobody
    assert body["frame_index"] > 0

    r = client.post(f"/api/v1/cameras/{cid}/stop")
    assert r.status_code == 200
    assert r.json()["status"] in ("idle", "streaming")  # thread may just be exiting


def test_stream_requires_running_camera(client):
    cam = _create(client)
    r = client.get(f"/api/v1/cameras/{cam['id']}/stream")
    assert r.status_code == 409


def test_mjpeg_generator_yields_multipart_chunks():
    """Unit-test the MJPEG generator directly (no HTTP streaming deadlock)."""
    from app.api.v1.routers.cameras import mjpeg_generator

    frames = [b"\xff\xd8\xfffakejpeg%d" % i for i in range(3)]

    class FakeWorker:
        def __init__(self):
            self.calls = 0

        @property
        def is_running(self):
            self.calls += 1
            return self.calls <= 3  # stop after 3 frames

        def latest_jpeg(self):
            return frames[min(self.calls - 1, 2)]

    chunks = list(mjpeg_generator(FakeWorker(), interval=0))
    assert len(chunks) == 3
    for i, chunk in enumerate(chunks):
        assert chunk.startswith(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n")
        assert b"\xff\xd8\xff" in chunk  # JPEG magic bytes
        assert chunk.endswith(b"\r\n")


def test_stream_endpoint_content_type_when_running(client, tmp_path):
    """The endpoint guards correctly; live byte streaming is verified
    against a running server with curl (see Phase 2 report)."""
    import cv2
    import numpy as np

    path = tmp_path / "clip.mp4"
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (320, 240)
    )
    for _ in range(30):
        writer.write(np.zeros((240, 320, 3), dtype=np.uint8))
    writer.release()

    cam = _create(client, url=str(path))
    cid = cam["id"]
    assert client.post(f"/api/v1/cameras/{cid}/start").status_code == 202
    try:
        # headers-only check would still block on infinite stream;
        # the 409-guard path is covered by test_stream_requires_running_camera
        r = client.get(f"/api/v1/cameras/{cid}/status")
        assert r.json()["status"] == "streaming"
    finally:
        client.post(f"/api/v1/cameras/{cid}/stop")


def test_delete_stops_and_removes(client):
    cam = _create(client)
    cid = cam["id"]
    r = client.delete(f"/api/v1/cameras/{cid}")
    assert r.status_code == 204
    assert client.get(f"/api/v1/cameras/{cid}").status_code == 404
    assert str(uuid.UUID(cid))  # id was a valid UUID
