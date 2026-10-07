"""Centroid tracker — stable temporary IDs across consecutive frames.

Simple, deterministic, testable. Matches detections to existing tracks by
nearest centroid within ``max_distance`` px. No DeepSORT/ByteTrack in MVP.
"""
from __future__ import annotations

import math

from app.vision.detector import Detection


def _centroid(det: Detection) -> tuple[float, float]:
    x1, y1, x2, y2 = det.bbox
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


class CentroidTracker:
    def __init__(self, max_distance: float = 60.0, max_missed: int = 10):
        self.max_distance = max_distance
        self.max_missed = max_missed
        self._next_id = 1
        # track_id -> {"centroid": (x, y), "missed": int}
        self._tracks: dict[int, dict] = {}

    @property
    def active_ids(self) -> list[int]:
        return sorted(self._tracks.keys())

    def update(self, detections: list[Detection]) -> list[Detection]:
        """Assign track_id to each detection; return the same objects."""
        centroids = [_centroid(d) for d in detections]
        assigned: dict[int, int] = {}  # detection idx -> track id
        used_tracks: set[int] = set()

        # Greedy nearest-neighbour matching.
        for i, c in enumerate(centroids):
            best_id: int | None = None
            best_dist = self.max_distance
            for tid, track in self._tracks.items():
                if tid in used_tracks:
                    continue
                dist = math.dist(c, track["centroid"])
                if dist < best_dist:
                    best_dist = dist
                    best_id = tid
            if best_id is not None:
                assigned[i] = best_id
                used_tracks.add(best_id)

        # Unmatched detections start new tracks.
        for i in range(len(detections)):
            if i not in assigned:
                tid = self._next_id
                self._next_id += 1
                assigned[i] = tid

        # Refresh matched tracks, age the rest.
        new_tracks: dict[int, dict] = {}
        for i, tid in assigned.items():
            new_tracks[tid] = {"centroid": centroids[i], "missed": 0}
        for tid, track in self._tracks.items():
            if tid not in new_tracks:
                missed = track["missed"] + 1
                if missed <= self.max_missed:
                    new_tracks[tid] = {
                        "centroid": track["centroid"],
                        "missed": missed,
                    }
        self._tracks = new_tracks

        for i, det in enumerate(detections):
            det.track_id = assigned[i]
        return detections

    def reset(self) -> None:
        self._tracks.clear()
        self._next_id = 1
