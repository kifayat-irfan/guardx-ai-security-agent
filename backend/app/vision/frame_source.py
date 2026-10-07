"""Frame sources — video file / webcam via OpenCV.

Clean lifecycle (open/read/close), frame iteration with index + timestamp,
and measured source FPS. New sources (e.g. RTSP reconnect, image folder)
implement the ``FrameSource`` interface and register in ``create_frame_source``.
"""
from __future__ import annotations

import abc
import time
from dataclasses import dataclass

import cv2
import numpy as np


class FrameSourceError(Exception):
    """Raised when a source cannot be opened or read."""


@dataclass
class Frame:
    image: np.ndarray  # BGR, uint8
    index: int
    timestamp: float  # seconds since source opened


class FrameSource(abc.ABC):
    """Interface every camera source must implement."""

    @abc.abstractmethod
    def open(self) -> None:
        """Open the underlying capture. Raises FrameSourceError."""

    @abc.abstractmethod
    def read(self) -> Frame | None:
        """Return the next frame, or None at end-of-stream."""

    @abc.abstractmethod
    def close(self) -> None:
        """Release all resources. Safe to call multiple times."""

    @property
    @abc.abstractmethod
    def source_fps(self) -> float:
        """Nominal FPS reported by the source (0 if unknown)."""

    def __enter__(self) -> "FrameSource":
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class OpenCVFrameSource(FrameSource):
    """File / webcam source backed by cv2.VideoCapture.

    ``loop=True`` (file sources only) rewinds at end-of-stream so a sample
    video behaves like a continuous demo feed.
    """

    def __init__(self, source_type: str, source_url: str, loop: bool = False):
        if source_type not in ("file", "webcam"):
            raise FrameSourceError(f"unsupported source_type: {source_type}")
        self.source_type = source_type
        self.loop = loop and source_type == "file"
        # webcam device index comes through as a string, e.g. "0"
        self.target: str | int = (
            int(source_url) if source_type == "webcam" else source_url
        )
        self._cap: cv2.VideoCapture | None = None
        self._index = 0
        self._t0 = 0.0
        self._opened = False
        self.loops_completed = 0

    def open(self) -> None:
        if self._opened:
            return
        if self.source_type == "file":
            import os

            if not os.path.isfile(self.target):
                raise FrameSourceError(f"video file not found: {self.target}")
        cap = cv2.VideoCapture(self.target)
        if not cap.isOpened():
            raise FrameSourceError(
                f"could not open {self.source_type} source: {self.target}"
            )
        self._cap = cap
        self._index = 0
        self._t0 = time.time()
        self._opened = True

    def read(self) -> Frame | None:
        if not self._opened or self._cap is None:
            raise FrameSourceError("source is not open")
        ok, image = self._cap.read()
        if (not ok or image is None) and self.loop:
            # rewind and try once more — continuous demo feed
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, image = self._cap.read()
            if ok and image is not None:
                self.loops_completed += 1
                self._index = 0
                self._t0 = time.time()
        if not ok or image is None:
            return None  # end of file / stream
        frame = Frame(
            image=image,
            index=self._index,
            timestamp=time.time() - self._t0,
        )
        self._index += 1
        return frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._opened = False

    @property
    def source_fps(self) -> float:
        if self._cap is None:
            return 0.0
        return float(self._cap.get(cv2.CAP_PROP_FPS) or 0.0)

    @property
    def is_open(self) -> bool:
        return self._opened


def create_frame_source(
    source_type: str, source_url: str, loop: bool = False
) -> FrameSource:
    """Factory — add new source types here without touching the detector."""
    if source_type in ("file", "webcam"):
        return OpenCVFrameSource(source_type, source_url, loop=loop)
    # Future: "rtsp" -> RtspFrameSource with reconnect logic
    raise FrameSourceError(f"unsupported source_type: {source_type}")
