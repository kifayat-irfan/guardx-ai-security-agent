"""Centroid tracker tests — ID stability, entry/exit, determinism."""
from app.vision.detector import Detection
from app.vision.tracker import CentroidTracker


def _det(cx, cy, w=40, h=80, conf=0.9):
    return Detection(
        bbox=[cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2],
        confidence=conf,
        frame_index=0,
    )


def test_stable_id_across_30_frames():
    tracker = CentroidTracker()
    first_id = None
    for i in range(30):
        # person walks slowly to the right
        (d,) = tracker.update([_det(100 + i * 3, 200)])
        if first_id is None:
            first_id = d.track_id
        assert d.track_id == first_id
    assert first_id == 1


def test_new_far_detection_gets_new_id():
    tracker = CentroidTracker()
    (a,) = tracker.update([_det(100, 100)])
    (b,) = tracker.update([_det(500, 400)])
    assert a.track_id != b.track_id
    assert tracker.active_ids == [1, 2]


def test_close_detections_keep_their_ids():
    tracker = CentroidTracker()
    ds = tracker.update([_det(100, 100), _det(400, 300)])
    ids_before = sorted(d.track_id for d in ds)
    ds2 = tracker.update([_det(102, 101), _det(398, 302)])
    assert sorted(d.track_id for d in ds2) == ids_before


def test_track_dropped_after_max_missed():
    tracker = CentroidTracker(max_missed=3)
    tracker.update([_det(100, 100)])
    assert tracker.active_ids == [1]
    for _ in range(3):
        tracker.update([])
    assert tracker.active_ids == [1]  # still within grace
    tracker.update([])
    assert tracker.active_ids == []  # dropped


def test_reappearing_person_gets_fresh_id_after_drop():
    tracker = CentroidTracker(max_missed=1)
    (a,) = tracker.update([_det(100, 100)])
    tracker.update([])
    tracker.update([])  # dropped now
    (b,) = tracker.update([_det(100, 100)])
    assert b.track_id != a.track_id


def test_reset_clears_state():
    tracker = CentroidTracker()
    tracker.update([_det(100, 100)])
    tracker.reset()
    assert tracker.active_ids == []
    (d,) = tracker.update([_det(100, 100)])
    assert d.track_id == 1
