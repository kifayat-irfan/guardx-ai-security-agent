"""Zone schemas — CRUD + validation (Phase 3).

Polygon input accepts two shapes, both normalized 0.0-1.0:
  - [[x, y], [x, y], ...]            (canonical, stored as-is)
  - [{"x": x, "y": y}, ...]          (object form, normalized on input)
"""
import uuid
from datetime import datetime
from typing import Union

from pydantic import BaseModel, Field, field_validator


def _normalize_polygon(value) -> list[list[float]]:
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("polygon must have at least 3 points")
    points: list[list[float]] = []
    for p in value:
        if isinstance(p, dict):
            if "x" not in p or "y" not in p:
                raise ValueError("polygon points need 'x' and 'y'")
            x, y = p["x"], p["y"]
        elif isinstance(p, (list, tuple)) and len(p) == 2:
            x, y = p
        else:
            raise ValueError(
                "polygon points must be [x, y] or {'x': x, 'y': y}"
            )
        x, y = float(x), float(y)
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise ValueError(
                f"polygon coordinates must be normalized 0.0-1.0, got [{x}, {y}]"
            )
        points.append([x, y])
    return points


class ZoneCreate(BaseModel):
    camera_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    polygon: Union[list[list[float]], list[dict]] = Field(min_length=3)
    dwell_seconds: float = Field(default=2.0, ge=0)
    cooldown_seconds: float = Field(default=60.0, ge=0)
    active: bool = True

    @field_validator("polygon", mode="before")
    @classmethod
    def _validate_polygon(cls, v):
        return _normalize_polygon(v)


class ZoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    polygon: Union[list[list[float]], list[dict]] | None = None
    dwell_seconds: float | None = Field(default=None, ge=0)
    cooldown_seconds: float | None = Field(default=None, ge=0)
    active: bool | None = None

    @field_validator("polygon", mode="before")
    @classmethod
    def _validate_polygon(cls, v):
        if v is None:
            return v
        return _normalize_polygon(v)


class ZoneRead(BaseModel):
    id: uuid.UUID
    camera_id: uuid.UUID
    name: str
    polygon: list[list[float]]
    dwell_seconds: float
    cooldown_seconds: float
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
