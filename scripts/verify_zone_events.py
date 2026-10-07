"""Phase 3 real-video verification.

Runs the real pipeline (video file -> YOLOv8n -> centroid tracker ->
ZoneEngine) over assets/test_videos/person_pan_test.mp4 with two restricted
zones, and prints the actual zone_enter / zone_exit events observed.

No invented numbers: everything printed comes from this run.
"""
import sys
import time
import uuid
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, "backend")

from app.vision.detector import PersonDetector  # noqa: E402
from app.vision.frame_source import create_frame_source  # noqa: E402
from app.vision.tracker import CentroidTracker  # noqa: E402
from app.zone_engine.engine import ZoneEngine  # noqa: E402
from app.zone_engine.events import ZoneEventType  # noqa: E402
from app.zone_engine.zone import ZoneConfig  # noqa: E402

CLIP = "assets/test_videos/person_pan_test.mp4"


def main() -> int:
    detector = PersonDetector()
    tracker = CentroidTracker()
    engine = ZoneEngine()
    cam_id = uuid.uuid4()
    zones = [
        ZoneConfig(
            id=uuid.uuid4(), camera_id=cam_id, name="middle-band",
            polygon=[[0.35, 0.0], [0.65, 0.0], [0.65, 1.0], [0.35, 1.0]],
            dwell_seconds=0.3, cooldown_seconds=0.0,
        ),
        ZoneConfig(
            id=uuid.uuid4(), camera_id=cam_id, name="left-band",
            polygon=[[0.02, 0.0], [0.28, 0.0], [0.28, 1.0], [0.02, 1.0]],
            dwell_seconds=0.3, cooldown_seconds=0.0,
        ),
    ]
    engine.set_zones(zones)

    events = []
    frames = 0
    t0 = time.perf_counter()
    with create_frame_source("file", CLIP, loop=True) as source:
        for _ in range(150):
            frame = source.read()
            frames += 1
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
    wall = time.perf_counter() - t0

    enters = [e for e in events if e.event_type == ZoneEventType.ZONE_ENTER]
    exits = [e for e in events if e.event_type == ZoneEventType.ZONE_EXIT]
    by_track: dict[int, list] = {}
    for e in events:
        by_track.setdefault(e.tracking_id, []).append(e.event_type)

    print(f"frames processed : {frames} in {wall:.1f}s wall")
    print(f"total events     : {len(events)}")
    print(f"zone_enter       : {len(enters)}")
    print(f"zone_exit        : {len(exits)}")
    print(f"distinct tracks  : {len(by_track)}")
    print(f"zones fired      : {sorted({e.zone_name for e in events})}")
    print("events:")
    for e in events:
        print(
            f"  {e.zone_name:11s} {e.event_type:10s} track={e.tracking_id} "
            f"t={e.timestamp:6.2f}s point={e.point} conf={e.confidence:.2f}"
        )

    # duplicate-enter suppression check
    dupes = 0
    for tid, types in by_track.items():
        for a, b in zip(types, types[1:]):
            if a == b == ZoneEventType.ZONE_ENTER:
                dupes += 1
    print(f"duplicate enters : {dupes}")

    ok = (
        len(enters) >= 1
        and len(exits) >= 1
        and dupes == 0
        and len(by_track) >= 2
        and {e.zone_name for e in events} == {"middle-band", "left-band"}
    )
    print("VERIFICATION:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
