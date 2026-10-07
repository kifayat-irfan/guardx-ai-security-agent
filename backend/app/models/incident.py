"""Incident ORM model (Phase 7) — PostgreSQL is the source of truth.

One row per analyzed zone event. Failed workflows are also stored (with
their failure status, no AI fields) so failures stay observable.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

UUIDType = Uuid  # native UUID on Postgres, CHAR(32) on SQLite


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    # original zone event identity
    external_event_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False,
                                                 index=True)
    zone_id: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False,
                                               index=True)
    zone_name: Mapped[str] = mapped_column(String(200), nullable=False,
                                           index=True)
    tracking_id: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False,
                                            index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        # wall-clock time the event was processed; the source-relative
        # frame timestamp lives in event_data
        DateTime(timezone=True),
        server_default=func.now(), nullable=False, index=True,
    )
    detection_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    bounding_box: Mapped[list] = mapped_column(JSON, nullable=False)
    point: Mapped[list] = mapped_column(JSON, nullable=False)
    # full original ZoneEvent (JSON dict) — allows exact reconstruction
    event_data: Mapped[dict] = mapped_column(JSON, nullable=False)

    # workflow outcome
    status: Mapped[str] = mapped_column(String(32), nullable=False,
                                        index=True)  # completed | *_failed ...
    severity: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, index=True
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text,
                                                              nullable=True)
    analysis_confidence: Mapped[Optional[float]] = mapped_column(Float,
                                                                 nullable=True)
    error: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    workflow_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    report: Mapped[Optional["IncidentReport"]] = relationship(
        "IncidentReport", back_populates="incident", uselist=False,
        cascade="all, delete-orphan",
    )
