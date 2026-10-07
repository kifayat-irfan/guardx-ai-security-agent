"""Integration tests — real YOLOv8n inference (downloads ~6MB weights once).

Slow by design; run with the rest of the suite in Phase 2 verification.
"""
import os

import cv2
import numpy as np
import pytest

from app.vision.detector import PERSON_CLASS_NAME, PersonDetector
from app.vision.frame_source import create_frame_source
from app.vision.tracker import CentroidTracker

FIXTURE = os.path.join(
    os.path.dirname(__file__), "..", "..", "assets", "test_videos", "bus.jpg"
)
FIXTURE = os.path.abspath(FIXTURE)

pytestmark = pytest.mark.skipif(
    not os.path.isfile(FIXTURE), reason=f"fixture missing: {FIXTURE}"
)


def _make_clip(path: str, n_frames: int = 30) -> None:
    img = cv2.imread(FIXTURE)
    assert img is not None
    ih, iw = img.shape[:2]
    W, H = 640, 480
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (W, H))
    assert writer.isOpened()
    for i in range(n_frames):
        x0 = int((iw - W) * (i / max(1, n_frames - 1)))
        crop = img[0:H, x0 : x0 + W]
        if crop.shape[1] < W:
            crop = np.hstack(
                [crop, np.zeros((H, W - crop.shape[1], 3), dtype=np.uint8)]
            )
        writer.write(crop)
    writer.release()


def test_real_inference_finds_people_in_fixture():
    det = PersonDetector(confidence=0.5)
    img = cv2.imread(FIXTURE)
    dets = det.detect(img)
    assert len(dets) >= 1, "expected at least one person in bus.jpg"
    assert all(d.class_name == PERSON_CLASS_NAME for d in dets)
    assert all(d.confidence >= 0.5 for d in dets)
    assert det.is_loaded
    assert det.last_inference_ms > 0


def test_full_pipeline_on_generated_clip(tmp_path):
    clip = str(tmp_path / "clip.mp4")
    _make_clip(clip, n_frames=30)

    det = PersonDetector(confidence=0.5)
    tracker = CentroidTracker()
    max_persons = 0
    frames = 0
    seen_ids: set[int] = set()

    with create_frame_source("file", clip) as src:
        while True:
            frame = src.read()
            if frame is None:
                break
            frames += 1
            dets = tracker.update(det.detect(frame.image, frame.index))
            max_persons = max(max_persons, len(dets))
            seen_ids.update(d.track_id for d in dets if d.track_id)

    assert frames == 30
    assert max_persons >= 1, "pipeline found no people in the test clip"
    assert len(seen_ids) >= 1
