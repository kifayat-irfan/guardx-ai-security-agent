"""Zone CRUD API tests (Phase 3). Uses the shared SQLite client fixture."""
import uuid


def _camera_id(client) -> str:
    r = client.post(
        "/api/v1/cameras",
        json={"name": "zone-test-cam", "source_type": "file",
              "source_url": "/tmp/x.mp4"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _zone_payload(cam_id, **kw):
    payload = {
        "camera_id": cam_id,
        "name": "door",
        "polygon": [[0.1, 0.2], [0.8, 0.2], [0.8, 0.8], [0.1, 0.8]],
    }
    payload.update(kw)
    return payload


def test_create_zone(client):
    cam = _camera_id(client)
    r = client.post("/api/v1/zones", json=_zone_payload(cam))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["camera_id"] == cam
    assert body["name"] == "door"
    assert body["active"] is True
    assert body["dwell_seconds"] == 2.0
    assert body["cooldown_seconds"] == 60.0
    assert "updated_at" in body


def test_create_zone_object_polygon_form(client):
    cam = _camera_id(client)
    r = client.post(
        "/api/v1/zones",
        json=_zone_payload(
            cam,
            polygon=[
                {"x": 0.1, "y": 0.2}, {"x": 0.8, "y": 0.2},
                {"x": 0.8, "y": 0.8}, {"x": 0.1, "y": 0.8},
            ],
        ),
    )
    assert r.status_code == 201, r.text
    assert r.json()["polygon"][0] == [0.1, 0.2]


def test_create_zone_rejects_short_polygon(client):
    cam = _camera_id(client)
    r = client.post("/api/v1/zones",
                    json=_zone_payload(cam, polygon=[[0.1, 0.1], [0.9, 0.9]]))
    assert r.status_code == 422


def test_create_zone_rejects_denormalized_coords(client):
    cam = _camera_id(client)
    r = client.post("/api/v1/zones",
                    json=_zone_payload(cam, polygon=[[0, 0], [2, 0], [1, 1]]))
    assert r.status_code == 422


def test_create_zone_rejects_unknown_camera(client):
    r = client.post("/api/v1/zones", json=_zone_payload(str(uuid.uuid4())))
    assert r.status_code == 404


def test_list_get_update_delete_zone(client):
    cam = _camera_id(client)
    zid = client.post("/api/v1/zones", json=_zone_payload(cam)).json()["id"]

    # list filtered by camera
    r = client.get("/api/v1/zones", params={"camera_id": cam})
    assert r.status_code == 200
    assert any(z["id"] == zid for z in r.json())

    # get
    r = client.get(f"/api/v1/zones/{zid}")
    assert r.status_code == 200
    assert r.json()["name"] == "door"

    # update: rename + disable
    r = client.patch(f"/api/v1/zones/{zid}",
                     json={"name": "gate", "active": False})
    assert r.status_code == 200
    assert r.json()["name"] == "gate"
    assert r.json()["active"] is False

    # delete
    r = client.delete(f"/api/v1/zones/{zid}")
    assert r.status_code == 204
    assert client.get(f"/api/v1/zones/{zid}").status_code == 404


def test_update_zone_rejects_bad_polygon(client):
    cam = _camera_id(client)
    zid = client.post("/api/v1/zones", json=_zone_payload(cam)).json()["id"]
    r = client.patch(f"/api/v1/zones/{zid}", json={"polygon": [[0, 0]]})
    assert r.status_code == 422
