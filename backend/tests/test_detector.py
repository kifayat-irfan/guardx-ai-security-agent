"""Detector tests — schema + person-only contract (model stubbed, no weights)."""
import numpy as np
import pytest

from app.vision.detector import (
    PERSON_CLASS_ID,
    PERSON_CLASS_NAME,
    Detection,
    PersonDetector,
)


class _FakeTensor:
    def __init__(self, values):
        self._v = np.array(values, dtype=np.float32)

    def __getitem__(self, i):
        return self._v[i]

    def tolist(self):
        return self._v.tolist()


class _FakeBox:
    def __init__(self, xyxy, conf):
        self.xyxy = _FakeTensor([xyxy])
        self.conf = _FakeTensor([conf])


class _FakeBoxes:
    def __init__(self, boxes):
        self._boxes = boxes

    def __iter__(self):
        return iter(self._boxes)


class _FakeResult:
    def __init__(self, boxes):
        self.boxes = _FakeBoxes(boxes)


class _FakeModel:
    """Stands in for ultralytics.YOLO; records predict kwargs."""

    def __init__(self, results):
        self._results = results
        self.calls = []

    def predict(self, image, **kwargs):
        self.calls.append(kwargs)
        return self._results


def _detector_with(results):
    det = PersonDetector(confidence=0.5)
    det._model = _FakeModel(results)  # skip lazy download
    # bypass _load()
    det._load = lambda: None
    return det


def test_detection_schema_fields():
    det = _detector_with(
        [_FakeResult([_FakeBox([10, 20, 30, 60], 0.87)])]
    )
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    out = det.detect(img, frame_index=3, timestamp=1.25)
    assert len(out) == 1
    d = out[0]
    assert isinstance(d, Detection)
    assert d.bbox == [10.0, 20.0, 30.0, 60.0]
    assert d.confidence == pytest.approx(0.87)
    assert d.class_id == PERSON_CLASS_ID
    assert d.class_name == PERSON_CLASS_NAME
    assert d.frame_index == 3
    assert d.timestamp == pytest.approx(1.25)
    assert d.track_id is None  # tracker assigns later
    # JSON-serializable for the status API
    d.model_dump_json()


def test_person_only_filter_requested_from_model():
    det = _detector_with([_FakeResult([])])
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    det.detect(img)
    assert det._model.calls, "predict was not called"
    assert det._model.calls[0]["classes"] == [PERSON_CLASS_ID]


def test_confidence_threshold_forwarded():
    det = PersonDetector(confidence=0.42)
    det._model = _FakeModel([_FakeResult([])])
    det._load = lambda: None
    det.detect(np.zeros((64, 64, 3), dtype=np.uint8))
    assert det._model.calls[0]["conf"] == pytest.approx(0.42)


def test_empty_result_gives_no_detections():
    det = _detector_with([_FakeResult([])])
    out = det.detect(np.zeros((64, 64, 3), dtype=np.uint8))
    assert out == []


def test_lazy_load_flag():
    det = PersonDetector()
    assert not det.is_loaded
