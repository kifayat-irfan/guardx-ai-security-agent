"""YOLO person detector — pretrained YOLOv8n, lazy model load.

Only the ``person`` class (COCO id 0) is returned. No custom training.
Model weights are downloaded once by ultralytics into the user cache
(never committed to git — see .gitignore ``*.pt``).
"""
from __future__ import annotations

import threading
import time

import numpy as np
from pydantic import BaseModel, Field

PERSON_CLASS_ID = 0
PERSON_CLASS_NAME = "person"


class Detection(BaseModel):
    """One structured person detection."""

    bbox: list[float] = Field(
        description="xyxy pixel coordinates [x1, y1, x2, y2]"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    class_id: int = PERSON_CLASS_ID
    class_name: str = PERSON_CLASS_NAME
    track_id: int | None = Field(
        default=None, description="centroid tracker ID (set by tracker)"
    )
    frame_index: int = 0
    timestamp: float = 0.0


class PersonDetector:
    """Thread-safe, lazily-loaded YOLOv8n person detector."""

    def __init__(
        self,
        model_name: str = "yolov8n.pt",
        confidence: float = 0.5,
        imgsz: int = 640,
        device: str | None = None,
    ):
        self.model_name = model_name
        self.confidence = confidence
        self.imgsz = imgsz
        self.device = device  # None -> ultralytics auto-select
        self._model = None
        self._lock = threading.Lock()
        self.last_inference_ms: float = 0.0

    def _load(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            from ultralytics import YOLO

            self._model = YOLO(self.model_name)

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def detect(
        self,
        image: np.ndarray,
        frame_index: int = 0,
        timestamp: float | None = None,
    ) -> list[Detection]:
        """Run inference; return person-only structured detections."""
        self._load()
        t0 = time.perf_counter()
        results = self._model.predict(
            image,
            conf=self.confidence,
            imgsz=self.imgsz,
            classes=[PERSON_CLASS_ID],
            verbose=False,
            device=self.device,
        )
        self.last_inference_ms = (time.perf_counter() - t0) * 1000.0

        ts = timestamp if timestamp is not None else time.time()
        detections: list[Detection] = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                xyxy = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                detections.append(
                    Detection(
                        bbox=[float(v) for v in xyxy],
                        confidence=conf,
                        class_id=PERSON_CLASS_ID,
                        class_name=PERSON_CLASS_NAME,
                        frame_index=frame_index,
                        timestamp=ts,
                    )
                )
        return detections
