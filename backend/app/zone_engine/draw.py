"""Draw restricted-zone polygons on frames (MJPEG overlay)."""
from __future__ import annotations

import cv2
import numpy as np

from app.zone_engine.zone import ZoneConfig

ZONE_COLOR = (0, 0, 255)  # red in BGR — restricted


def draw_zones(image: np.ndarray, zones: list[ZoneConfig]) -> np.ndarray:
    """Return a copy of the frame with zone polygons + names drawn."""
    out = image.copy()
    h, w = out.shape[:2]
    for zone in zones:
        pts = np.array(
            [[int(x * w), int(y * h)] for x, y in zone.polygon], dtype=np.int32
        )
        if len(pts) < 3:
            continue
        overlay = out.copy()
        cv2.fillPoly(overlay, [pts], ZONE_COLOR)
        cv2.addWeighted(overlay, 0.15, out, 0.85, 0, out)
        cv2.polylines(out, [pts], isClosed=True, color=ZONE_COLOR, thickness=2)
        x, y = pts[0]
        label = f"RESTRICTED: {zone.name}"
        (tw, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(out, (x, y - 22), (x + tw + 8, y), ZONE_COLOR, -1)
        cv2.putText(
            out, label, (x + 4, y - 7),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA,
        )
    return out
