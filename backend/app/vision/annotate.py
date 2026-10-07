"""Frame annotation — draw detections + HUD text for the MJPEG stream."""
from __future__ import annotations

import cv2
import numpy as np

from app.vision.detector import Detection

BOX_COLOR = (0, 255, 255)  # cyan-ish in BGR
TEXT_COLOR = (0, 255, 255)
FPS_COLOR = (0, 255, 0)


def annotate_frame(
    image: np.ndarray,
    detections: list[Detection],
    fps: float | None = None,
) -> np.ndarray:
    """Return a copy of the frame with boxes, IDs, confidence and FPS."""
    out = image.copy()
    for det in detections:
        x1, y1, x2, y2 = (int(v) for v in det.bbox)
        cv2.rectangle(out, (x1, y1), (x2, y2), BOX_COLOR, 2)
        label = f"{det.class_name}"
        if det.track_id is not None:
            label += f" #{det.track_id}"
        label += f" {det.confidence:.2f}"
        (w, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(out, (x1, y1 - 20), (x1 + w + 6, y1), BOX_COLOR, -1)
        cv2.putText(
            out, label, (x1 + 3, y1 - 6),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA,
        )
    if fps is not None:
        cv2.putText(
            out, f"FPS {fps:.1f}", (12, 28),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, FPS_COLOR, 2, cv2.LINE_AA,
        )
        cv2.putText(
            out, f"persons: {len(detections)}", (12, 56),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, FPS_COLOR, 2, cv2.LINE_AA,
        )
    return out


def encode_jpeg(image: np.ndarray, quality: int = 80) -> bytes:
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("JPEG encoding failed")
    return buf.tobytes()
