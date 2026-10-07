"""ZoneConfig — engine-side view of a zone (built from the DB model)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class ZoneConfig:
    id: uuid.UUID
    camera_id: uuid.UUID
    name: str
    polygon: list[list[float]]  # normalized [[x, y], ...], >= 3 points
    dwell_seconds: float = 2.0
    cooldown_seconds: float = 60.0
    active: bool = True
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_orm(cls, zone) -> "ZoneConfig":
        return cls(
            id=zone.id,
            camera_id=zone.camera_id,
            name=zone.name,
            polygon=[list(p) for p in zone.polygon],
            dwell_seconds=float(zone.dwell_seconds),
            cooldown_seconds=float(zone.cooldown_seconds),
            active=bool(zone.active),
        )
