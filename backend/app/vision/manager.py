"""CameraManager — owns the live CameraWorker per camera (singleton)."""
from __future__ import annotations

import threading
import uuid

from app.models.camera import Camera
from app.vision.camera_worker import CameraWorker


class CameraAlreadyRunning(Exception):
    pass


class CameraManager:
    def __init__(self):
        self._workers: dict[uuid.UUID, CameraWorker] = {}
        self._lock = threading.Lock()

    def start(
        self, camera: Camera, frame_skip: int = 2, loop: bool = True
    ) -> CameraWorker:
        with self._lock:
            existing = self._workers.get(camera.id)
            if existing is not None and existing.is_running:
                raise CameraAlreadyRunning(str(camera.id))
            if existing is not None:
                self._workers.pop(camera.id, None)
            worker = CameraWorker(
                camera_id=camera.id,
                source_type=camera.source_type,
                source_url=camera.source_url,
                frame_skip=frame_skip,
                loop=loop,
            )
            self._workers[camera.id] = worker
        worker.start()
        return worker

    def stop(self, camera_id: uuid.UUID) -> bool:
        with self._lock:
            worker = self._workers.pop(camera_id, None)
        if worker is None:
            return False
        worker.stop()
        return True

    def get_worker(self, camera_id: uuid.UUID) -> CameraWorker | None:
        with self._lock:
            return self._workers.get(camera_id)

    def running_ids(self) -> list[str]:
        with self._lock:
            return [str(cid) for cid, w in self._workers.items() if w.is_running]


manager = CameraManager()
"""Process-wide camera manager singleton."""
