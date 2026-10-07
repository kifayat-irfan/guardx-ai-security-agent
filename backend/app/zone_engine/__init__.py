"""Restricted-zone engine — determines whether tracked people are inside
configured polygon zones. No AI decisions here; it emits zone_enter /
zone_exit events for Phase 4+ to consume."""
from app.zone_engine.engine import ZoneEngine  # noqa: F401
from app.zone_engine.events import ZoneEvent, ZoneEventType  # noqa: F401
from app.zone_engine.geometry import bottom_center, point_in_polygon  # noqa: F401
from app.zone_engine.zone import ZoneConfig  # noqa: F401
