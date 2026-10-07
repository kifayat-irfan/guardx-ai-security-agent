"""ZoneEngine behavior tests — deterministic synthetic detections.

Frame is 100x100 px; engine normalizes to 0-1. Zone A covers the middle
band x in [0.4, 0.6]; zone B covers the right band x in [0.7, 0.9].
"""
import uuid

from app.vision.detector import Detection
from app.zone_engine.engine import ZoneEngine
from app.zone_engine.events import ZoneEventType
from app.zone_engine.zone import ZoneConfig

W = H = 100
CAM = uuid.uuid4()


def make_zone(name="zone-a", poly=None, dwell=1.0, cooldown=10.0, active=True,
              camera_id=CAM):
    return ZoneConfig(
        id=uuid.uuid4(),
        camera_id=camera_id,
        name=name,
        polygon=poly or [[0.4, 0.0], [0.6, 0.0], [0.6, 1.0], [0.4, 1.0]],
        dwell_seconds=dwell,
        cooldown_seconds=cooldown,
        active=active,
    )


def det(track_id, x_center, y_bottom=90, conf=0.9, ts=0.0):
    """Synthetic person detection; bottom-center at (x_center, y_bottom)."""
    return Detection(
        bbox=[x_center - 10, y_bottom - 40, x_center + 10, y_bottom],
        confidence=conf,
        track_id=track_id,
        timestamp=ts,
    )


def feed(engine, camera_id, track_positions, dt=0.5, start=0.0):
    """Feed frames; track_positions: list of dict track_id -> x_center."""
    events = []
    t = start
    for positions in track_positions:
        dets = [det(tid, x, ts=t) for tid, x in positions.items()]
        events += engine.update(camera_id, dets, t, W, H)
        events += engine.sweep(camera_id, set(positions), t)
        t += dt
    return events


def test_outside_to_inside_generates_enter():
    eng = ZoneEngine()
    eng.set_zones([make_zone(dwell=0.0)])
    events = feed(eng, CAM, [{1: 10}, {1: 50}])  # outside -> inside
    assert len(events) == 1
    ev = events[0]
    assert ev.event_type == "zone_enter"
    assert ev.tracking_id == 1
    assert ev.zone_name == "zone-a"
    assert ev.camera_id == CAM
    assert ev.point == [0.5, 0.9]
    assert ev.bounding_box == [0.4, 0.5, 0.6, 0.9]
    assert ev.confidence == 0.9


def test_inside_to_inside_does_not_repeat_enter():
    eng = ZoneEngine()
    eng.set_zones([make_zone(dwell=0.0)])
    events = feed(eng, CAM, [{1: 50}, {1: 52}, {1: 48}, {1: 55}])
    enters = [e for e in events if e.event_type == "zone_enter"]
    assert len(enters) == 1


def test_inside_to_outside_generates_exit():
    eng = ZoneEngine()
    eng.set_zones([make_zone(dwell=0.0)])
    events = feed(eng, CAM, [{1: 50}, {1: 50}, {1: 10}])
    types = [e.event_type for e in events]
    assert types == ["zone_enter", "zone_exit"]


def test_dwell_suppresses_flicker():
    eng = ZoneEngine()
    eng.set_zones([make_zone(dwell=2.0)])
    # inside for 1.0s (< dwell), then outside -> no events at all
    events = feed(eng, CAM, [{1: 50}, {1: 52}, {1: 10}], dt=0.5)
    assert events == []


def test_dwell_fires_after_threshold():
    eng = ZoneEngine()
    eng.set_zones([make_zone(dwell=1.0)])
    # inside continuously for 1.5s -> enter fires at t=1.0
    events = feed(eng, CAM, [{1: 50}, {1: 52}, {1: 48}, {1: 55}], dt=0.5)
    enters = [e for e in events if e.event_type == "zone_enter"]
    assert len(enters) == 1
    assert enters[0].timestamp == 1.0
    assert enters[0].metadata["dwell_elapsed"] >= 1.0


def test_cooldown_suppresses_immediate_reentry():
    eng = ZoneEngine()
    eng.set_zones([make_zone(dwell=0.0, cooldown=60.0)])
    events = feed(
        eng, CAM,
        [{1: 50}, {1: 10}, {1: 50}, {1: 50}],  # enter, exit, re-enter quickly
        dt=1.0,
    )
    enters = [e for e in events if e.event_type == "zone_enter"]
    exits = [e for e in events if e.event_type == "zone_exit"]
    assert len(enters) == 1
    assert len(exits) == 1


def test_cooldown_expires_allows_reentry():
    eng = ZoneEngine()
    eng.set_zones([make_zone(dwell=0.0, cooldown=2.0)])
    events = feed(
        eng, CAM,
        [{1: 50}, {1: 10}, {1: 50}, {1: 50}],  # re-enter after cooldown
        dt=1.0, start=0.0,
    )
    # t=0 enter, t=1 exit, t=2 re-enter (cooldown 2.0 elapsed), t=3 inside
    enters = [e for e in events if e.event_type == "zone_enter"]
    assert len(enters) == 2


def test_multiple_tracking_ids_independent():
    eng = ZoneEngine()
    eng.set_zones([make_zone(dwell=0.0)])
    events = feed(eng, CAM, [{1: 50, 2: 10}, {1: 50, 2: 55}])
    enters = {e.tracking_id for e in events if e.event_type == "zone_enter"}
    assert enters == {1, 2}


def test_multiple_zones():
    zone_b = make_zone(name="zone-b",
                       poly=[[0.7, 0.0], [0.9, 0.0], [0.9, 1.0], [0.7, 1.0]],
                       dwell=0.0)
    eng = ZoneEngine()
    eng.set_zones([make_zone(dwell=0.0), zone_b])
    events = feed(eng, CAM, [{1: 80}])  # inside zone-b only
    assert len(events) == 1
    assert events[0].zone_name == "zone-b"
    assert events[0].zone_id == zone_b.id


def test_multiple_cameras_isolated():
    cam2 = uuid.uuid4()
    eng = ZoneEngine()
    eng.set_zones([make_zone(dwell=0.0)])
    ev1 = eng.update(CAM, [det(1, 50, ts=0.0)], 0.0, W, H)
    ev2 = eng.update(cam2, [det(1, 50, ts=0.0)], 0.0, W, H)
    assert len(ev1) == 1 and len(ev2) == 1
    assert ev1[0].camera_id == CAM
    assert ev2[0].camera_id == cam2


def test_disabled_zone_ignored():
    eng = ZoneEngine()
    eng.set_zones([make_zone(dwell=0.0, active=False)])
    events = feed(eng, CAM, [{1: 50}])
    assert events == []
    assert eng.zones == []


def test_vanished_track_fires_exit():
    eng = ZoneEngine(max_missed=2)
    eng.set_zones([make_zone(dwell=0.0)])
    events = feed(eng, CAM, [{1: 50}, {}, {}, {}], dt=0.5)
    types = [e.event_type for e in events]
    assert types == ["zone_enter", "zone_exit"]
    assert events[1].metadata["reason"] == "track_expired"


def test_event_schema_fields():
    eng = ZoneEngine()
    eng.set_zones([make_zone(dwell=0.0)])
    events = feed(eng, CAM, [{1: 50}])
    ev = events[0]
    for f in ("event_id", "camera_id", "zone_id", "zone_name", "tracking_id",
              "event_type", "timestamp", "confidence", "bounding_box",
              "point", "metadata"):
        assert hasattr(ev, f), f"missing field {f}"
    assert ev.event_type in (ZoneEventType.ZONE_ENTER, "zone_enter")
