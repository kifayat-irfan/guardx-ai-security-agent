"""Camera worker — background thread running the vision loop.

Pipeline per camera: frame_source -> (frame_skip) -> detector -> tracker
-> annotate -> latest JPEG. Exposes rolling FPS, person count and the latest
detections for the API. DB ``cameras.status`` mirrors the lifecycle.
"""
from __future__ import annotations

import threading
import time
import uuid

from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.models.camera import Camera
from app.vision.annotate import annotate_frame, encode_jpeg
from app.vision.detector import Detection, PersonDetector
from app.vision.frame_source import FrameSourceError, create_frame_source
from app.vision.tracker import CentroidTracker

logger = get_logger(__name__)


class CameraWorker(threading.Thread):
    def __init__(
        self,
        camera_id: uuid.UUID,
        source_type: str,
        source_url: str,
        frame_skip: int = 2,
        detector: PersonDetector | None = None,
        loop: bool = True,
    ):
        super().__init__(daemon=True, name=f"guardx-camera-{str(camera_id)[:8]}")
        self.camera_id = camera_id
        self.source_type = source_type
        self.source_url = source_url
        self.frame_skip = max(1, frame_skip)
        self.loop = loop
        self.detector = detector or self._default_detector()
        self.tracker = CentroidTracker()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._latest_jpeg: bytes | None = None
        self._detections: list[Detection] = []
        self._fps = 0.0
        self._frame_index = 0
        self._error: str | None = None
        self._running = False

    # -- lifecycle -----------------------------------------------------
    def run(self) -> None:
        self._running = True
        self._set_db_status("streaming")
        logger.info("camera %s: worker started (%s)", self.camera_id, self.source_url)
        try:
            source = create_frame_source(
                self.source_type, self.source_url, loop=self.loop
            )
            with source:
                self._loop(source)
        except FrameSourceError as exc:
            self._error = str(exc)
            self._set_db_status("error")
            logger.error("camera %s: %s", self.camera_id, exc)
        except Exception as exc:  # noqa: BLE001 - worker must not die silently
            self._error = str(exc)[:300]
            self._set_db_status("error")
            logger.exception("camera %s: worker crashed", self.camera_id)
        finally:
            self._running = False
            if self._error is None:
                self._set_db_status("idle")
            logger.info("camera %s: worker stopped", self.camera_id)

    def _loop(self, source) -> None:
        ema_fps = 0.0
        last_detections: list[Detection] = []
        while not self._stop_event.is_set():
            t0 = time.perf_counter()
            frame = source.read()
            if frame is None:
                logger.info("camera %s: end of stream", self.camera_id)
                break
            if frame.index % self.frame_skip == 0:
                dets = self.detector.detect(
                    frame.image,
                    frame_index=frame.index,
                    timestamp=frame.timestamp,
                )
                # keep last detections across skipped frames: stable overlay
                # and person_count (no flicker to zero between inferences)
                last_detections = self.tracker.update(dets)
                with self._lock:
                    self._detections = last_detections
            annotated = annotate_frame(
                frame.image, last_detections, fps=ema_fps or None
            )
            jpeg = encode_jpeg(annotated)
            with self._lock:
                self._latest_jpeg = jpeg
                self._frame_index = frame.index
            dt = time.perf_counter() - t0
            inst = 1.0 / dt if dt > 0 else 0.0
            ema_fps = inst if ema_fps == 0 else 0.9 * ema_fps + 0.1 * inst
            with self._lock:
                self._fps = ema_fps

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        self.join(timeout=timeout)

    @property
    def is_running(self) -> bool:
        return self._running and self.is_alive()

    # -- state for the API ---------------------------------------------
    def snapshot(self) -> dict:
        with self._lock:
            return {
                "camera_id": str(self.camera_id),
                "status": "streaming" if self.is_running else "idle",
                "fps": round(self._fps, 1),
                "person_count": len(self._detections),
                "frame_index": self._frame_index,
                "inference_ms": round(self.detector.last_inference_ms, 1),
                "error": self._error,
                "detections": [d.model_dump() for d in self._detections],
            }

    def latest_jpeg(self) -> bytes | None:
        with self._lock:
            return self._latest_jpeg

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _default_detector() -> PersonDetector:
        from app.core.config import get_settings

        s = get_settings()
        return PersonDetector(
            model_name=s.yolo_model,
            confidence=s.yolo_confidence,
            imgsz=s.yolo_imgsz,
        )

    def _set_db_status(self, status: str) -> None:
        try:
            db = SessionLocal()
            try:
                cam = db.get(Camera, self.camera_id)
                if cam is not None:
                    cam.status = status
                    db.commit()
            finally:
                db.close()
        except Exception:  # noqa: BLE001 - status mirror must not break the loop
            logger.warning("camera %s: could not persist status", self.camera_id)
