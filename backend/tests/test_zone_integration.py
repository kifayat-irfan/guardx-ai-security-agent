"""Camera + zone engine integration on the real Phase 2 test clip.

Runs the REAL pipeline (file source -> YOLOv8n -> centroid tracker ->
ZoneEngine) over assets/test_videos/person_pan_test.mp4 with two zones
(middle band + right band). The clip loops; the camera pans right so people
drift leftward across the frame: they must ENTER zones and later EXIT them.
"""
import os
import uuid

import pytest

from app.vision.detector import PersonDetector
from app.vision.frame_source import create_frame_source
from app.vision.tracker import CentroidTracker
from app.zone_engine.engine import ZoneEngine
from app.zone_engine.events import ZoneEventType
from app.zone_engine.zone import ZoneConfig

CLIP = os.path.join(
    os.path.dirname(__file__), "..", "..", "assets", "test_videos",
    "person_pan_test.mp4",
)

pytestmark = pytest.mark.skipif(
    not os.path.exists(CLIP), reason="test clip missing"
)


def test_real_pipeline_produces_enter_and_exit():
    detector = PersonDetector()
    tracker = CentroidTracker()
    engine = ZoneEngine()
    cam_id = uuid.uuid4()
    zone_mid = ZoneConfig(
        id=uuid.uuid4(),
        camera_id=cam_id,
        name="middle-band",
        polygon=[[0.35, 0.0], [0.65, 0.0], [0.65, 1.0], [0.35, 1.0]],
        dwell_seconds=0.3,  # short dwell: clip is only 60 frames
        cooldown_seconds=0.0,
    )
    zone_left = ZoneConfig(
        id=uuid.uuid4(),
        camera_id=cam_id,
        name="left-band",
        polygon=[[0.02, 0.0], [0.28, 0.0], [0.28, 1.0], [0.02, 1.0]],
        dwell_seconds=0.3,
        cooldown_seconds=0.0,
    )
    engine.set_zones([zone_mid, zone_left])

    events = []
    with create_frame_source("file", CLIP, loop=True) as source:
        for i in range(150):  # looped: several pan cycles, more crossings
            frame = source.read()
            h, w = frame.image.shape[:2]
            dets = detector.detect(
                frame.image, frame_index=frame.index, timestamp=frame.timestamp
            )
            tracked = tracker.update(dets)
            events += engine.update(cam_id, tracked, frame.timestamp, w, h)
            events += engine.sweep(
                cam_id,
                {d.track_id for d in tracked if d.track_id is not None},
                frame.timestamp,
            )

    enters = [e for e in events if e.event_type == ZoneEventType.ZONE_ENTER]
    exits = [e for e in events if e.event_type == ZoneEventType.ZONE_EXIT]
    print(f"\nevents: {len(events)} enters: {len(enters)} exits: {len(exits)}")
    for e in events[:8]:
        print(f"  {e.event_type} track={e.tracking_id} t={e.timestamp:.2f}"
              f" point={e.point} conf={e.confidence:.2f}")

    # every event must reference a real configured zone and sane geometry
    zone_ids = {zone_mid.id, zone_left.id}
    for e in events:
        assert e.zone_id in zone_ids
        assert e.zone_name in ("middle-band", "left-band")
        assert 0.0 <= e.point[0] <= 1.0 and 0.0 <= e.point[1] <= 1.0

    assert len(enters) >= 1, "expected at least one zone_enter on the pan clip"
    assert len(exits) >= 1, "expected at least one zone_exit on the pan clip"
    # multiple zones: both configured zones fired on the real clip
    fired_zones = {e.zone_name for e in events}
    assert fired_zones == {"middle-band", "left-band"}, fired_zones

    # duplicate-enter suppression: never two enters in a row for one track
    by_track: dict[int, list] = {}
    for e in events:
        by_track.setdefault(e.tracking_id, []).append(e.event_type)
    for track_id, types in by_track.items():
        for a, b in zip(types, types[1:]):
            assert not (a == b == ZoneEventType.ZONE_ENTER), (
                f"duplicate enter for track {track_id}"
            )

    # multiple people: the clip has 2-3 persons; at least 2 distinct tracks
    # should interact with the zone
    assert len(by_track) >= 2, f"expected >=2 tracks, got {list(by_track)}"
