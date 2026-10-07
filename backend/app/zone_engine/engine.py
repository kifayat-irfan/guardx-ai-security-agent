"""ZoneEngine — per-camera restricted-zone state machine.

For every (zone, tracking_id) pair it tracks:
  outside -> pending (inside, dwell not yet met) -> inside (enter fired)

Rules:
  - zone_enter fires only after the person is continuously inside for
    dwell_seconds (flicker killer).
  - After an enter, no new enter for the same (zone, track) until
    cooldown_seconds have passed (spam guard).
  - zone_exit fires on inside -> outside.
  - A track that vanishes while inside/pending fires zone_exit on expiry.
  - Disabled zones are never loaded into the engine (see set_zones).

All timestamps are frame-time seconds (float). Deterministic: same input
sequence -> same event sequence.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field

from app.vision.detector import Detection
from app.zone_engine.events import ZoneEvent, ZoneEventType
from app.zone_engine.geometry import bottom_center, point_in_polygon
from app.zone_engine.zone import ZoneConfig

_OUTSIDE = "outside"
_PENDING = "pending"
_INSIDE = "inside"


@dataclass
class _TrackState:
    state: str = _OUTSIDE
    pending_since: float | None = None
    inside_since: float | None = None
    last_enter_at: float | None = None
    missed: int = 0
    # last known detection geometry (for track_expired exits)
    last_point: list[float] = field(default_factory=list)
    last_bbox: list[float] = field(default_factory=list)
    last_confidence: float = 0.0


class ZoneEngine:
    def __init__(self, max_missed: int = 10):
        self.max_missed = max_missed
        self._zones: dict[uuid.UUID, ZoneConfig] = {}
        # state key: (camera_id, zone_id, track_id)
        self._states: dict[tuple[uuid.UUID, uuid.UUID, int], _TrackState] = {}
        self._pending_events: list[ZoneEvent] = []
        self._lock = threading.Lock()

    # -- configuration -------------------------------------------------
    def set_zones(self, zones: list[ZoneConfig]) -> None:
        """Replace the zone set (only active zones should be passed)."""
        with self._lock:
            self._zones = {z.id: z for z in zones if z.active}
            # drop state for zones that no longer exist
            self._states = {
                k: v for k, v in self._states.items() if k[1] in self._zones
            }

    @property
    def zones(self) -> list[ZoneConfig]:
        with self._lock:
            return list(self._zones.values())

    # -- per-frame evaluation -------------------------------------------
    def update(
        self,
        camera_id: uuid.UUID,
        detections: list[Detection],
        timestamp: float,
        frame_width: int = 1,
        frame_height: int = 1,
    ) -> list[ZoneEvent]:
        """Evaluate detections against all zones; return new events."""
        with self._lock:
            return self._update_locked(camera_id, detections, timestamp,
                                       frame_width, frame_height)

    def _update_locked(
        self,
        camera_id: uuid.UUID,
        detections: list[Detection],
        timestamp: float,
        frame_width: int = 1,
        frame_height: int = 1,
    ) -> list[ZoneEvent]:
        for det in detections:
            if det.track_id is None:
                continue
            # bottom-center in normalized coords
            bc = bottom_center(det.bbox)
            norm_pt = [bc[0] / frame_width, bc[1] / frame_height]
            norm_bbox = [
                det.bbox[0] / frame_width,
                det.bbox[1] / frame_height,
                det.bbox[2] / frame_width,
                det.bbox[3] / frame_height,
            ]
            for zone in self._zones.values():
                inside = point_in_polygon(norm_pt, zone.polygon)
                self._transition(
                    camera_id, zone, det, norm_pt, norm_bbox, inside, timestamp
                )
        events = self._pending_events
        self._pending_events = []
        return events

    def sweep(
        self, camera_id: uuid.UUID, seen_track_ids: set[int], timestamp: float
    ) -> list[ZoneEvent]:
        """Expire tracks not seen recently; inside tracks fire zone_exit."""
        with self._lock:
            return self._sweep_locked(camera_id, seen_track_ids, timestamp)

    def _sweep_locked(
        self, camera_id: uuid.UUID, seen_track_ids: set[int], timestamp: float
    ) -> list[ZoneEvent]:
        for (cam_id, zone_id, track_id), st in list(self._states.items()):
            if cam_id != camera_id:
                continue
            if track_id in seen_track_ids:
                st.missed = 0
                continue
            st.missed += 1
            if st.missed > self.max_missed:
                zone = self._zones.get(zone_id)
                if zone is not None and st.state == _INSIDE:
                    self._emit(
                        camera_id, zone, track_id, ZoneEventType.ZONE_EXIT,
                        timestamp, confidence=st.last_confidence,
                        bbox=st.last_bbox, point=st.last_point,
                        metadata={"reason": "track_expired", "missed": st.missed},
                    )
                del self._states[(cam_id, zone_id, track_id)]
        events = self._pending_events
        self._pending_events = []
        return events

    # -- state machine ----------------------------------------------------
    def _transition(
        self,
        camera_id: uuid.UUID,
        zone: ZoneConfig,
        det: Detection,
        point: list[float],
        bbox: list[float],
        inside: bool,
        timestamp: float,
    ) -> None:
        key = (camera_id, zone.id, det.track_id)
        st = self._states.get(key)
        if st is None:
            st = _TrackState()
            self._states[key] = st
        st.last_point = point
        st.last_bbox = bbox
        st.last_confidence = det.confidence

        if inside:
            if st.state == _OUTSIDE:
                st.state = _PENDING
                st.pending_since = timestamp
            if st.state == _PENDING:
                _ps = st.pending_since if st.pending_since is not None else timestamp
                dwell_ok = (timestamp - _ps) >= zone.dwell_seconds
                cooldown_ok = (
                    st.last_enter_at is None
                    or (timestamp - st.last_enter_at) >= zone.cooldown_seconds
                )
                if dwell_ok and cooldown_ok:
                    st.state = _INSIDE
                    st.inside_since = timestamp
                    st.last_enter_at = timestamp
                    self._emit(
                        camera_id, zone, det.track_id, ZoneEventType.ZONE_ENTER,
                        timestamp, det.confidence, bbox, point,
                        metadata={
                            "dwell_elapsed": round(timestamp - _ps, 2),
                        },
                    )
                # else: still pending — dwell or cooldown not met, no event
            # _INSIDE + inside -> nothing (no repeated enter events)
        else:
            if st.state == _PENDING:
                st.state = _OUTSIDE  # flicker killed, no event
                st.pending_since = None
            elif st.state == _INSIDE:
                st.state = _OUTSIDE
                _is = st.inside_since if st.inside_since is not None else timestamp
                self._emit(
                    camera_id, zone, det.track_id, ZoneEventType.ZONE_EXIT,
                    timestamp, det.confidence, bbox, point,
                    metadata={
                        "inside_duration": round(timestamp - _is, 2),
                    },
                )
                st.inside_since = None
            # _OUTSIDE + outside -> nothing

    def _emit(self, camera_id, zone, track_id, event_type, timestamp,
              confidence, bbox, point, metadata) -> None:
        self._pending_events.append(
            ZoneEvent(
                camera_id=camera_id,
                zone_id=zone.id,
                zone_name=zone.name,
                tracking_id=track_id,
                event_type=event_type,
                timestamp=round(timestamp, 3),
                confidence=confidence,
                bounding_box=[round(v, 4) for v in bbox],
                point=[round(v, 4) for v in point],
                metadata={
                    **metadata,
                    "dwell_seconds": zone.dwell_seconds,
                    "cooldown_seconds": zone.cooldown_seconds,
                },
            )
        )

    # -- introspection (status API / Phase 4+) ----------------------------
    def track_states(self) -> list[dict]:
        with self._lock:
            return self._track_states_locked()

    def _track_states_locked(self) -> list[dict]:
        out = []
        for (cam_id, zone_id, track_id), st in self._states.items():
            zone = self._zones.get(zone_id)
            out.append(
                {
                    "camera_id": str(cam_id),
                    "zone_id": str(zone_id),
                    "zone_name": zone.name if zone else "?",
                    "tracking_id": track_id,
                    "state": st.state,
                    "inside_since": st.inside_since,
                }
            )
        return out

    def reset(self) -> None:
        with self._lock:
            self._states.clear()
            self._pending_events.clear()
