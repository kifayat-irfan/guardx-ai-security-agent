"""Deterministic geometry helpers for the zone engine.

Coordinate convention (documented for the whole project):
  - Polygons are lists of [x, y] pairs in NORMALIZED coordinates,
    0.0 <= x <= 1.0 and 0.0 <= y <= 1.0, relative to the frame.
  - x=0 is the left edge, y=0 is the top edge (image coordinates).
  - A detection's reference point is the BOTTOM-CENTER of its bbox
    (x_center, y_bottom) — approximating the person's feet on the ground.
"""
from __future__ import annotations


def bottom_center(bbox: list[float]) -> list[float]:
    """Bottom-center point of an xyxy bbox, in the bbox's own units."""
    x1, y1, x2, y2 = bbox
    return [(x1 + x2) / 2.0, y2]


def point_in_polygon(point: list[float] | tuple[float, float],
                     polygon: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon. Points exactly on an edge count as inside.

    Pure Python — deterministic, no OpenCV dependency, easy to unit test.
    """
    x, y = point
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        # point on segment -> inside
        if _on_segment(x, y, xi, yi, xj, yj):
            return True
        if (yi > y) != (yj > y):
            xinters = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < xinters:
                inside = not inside
        j = i
    return inside


def _on_segment(px: float, py: float,
                x1: float, y1: float, x2: float, y2: float) -> bool:
    """True if point (px,py) lies on segment (x1,y1)-(x2,y2)."""
    # cross product ~ 0 and within bounding box
    cross = (px - x1) * (y2 - y1) - (py - y1) * (x2 - x1)
    if abs(cross) > 1e-9:
        return False
    dot = (px - x1) * (px - x2) + (py - y1) * (py - y2)
    return dot <= 1e-9


def normalize_point_to_frame(point: list[float], width: int, height: int
                             ) -> tuple[int, int]:
    """Denormalize a 0-1 point to integer pixel coordinates."""
    return (int(point[0] * width), int(point[1] * height))
