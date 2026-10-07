"""IncidentReport ORM model (Phase 7).

One report per incident (unique incident_id). Reprocessing replaces the
report rather than adding another row. Citations are copied verbatim from
the validated LangGraph decision — never generated here.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

UUIDType = Uuid


class IncidentReport(Base):
    __tablename__ = "incident_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    report_type: Mapped[str] = mapped_column(String(32), nullable=False,
                                             default="ai_analysis")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text,
                                                              nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # exact citation IDs from the validated decision (citation guard passed)
    cited_policy_chunk_ids: Mapped[list] = mapped_column(JSON, nullable=False,
                                                         default=list)
    retrieved_policy_count: Mapped[int] = mapped_column(Integer, nullable=False,
                                                        default=0)
    # chunk IDs that were retrieved (for audit / re-derivation)
    retrieved_chunk_ids: Mapped[list] = mapped_column(JSON, nullable=False,
                                                      default=list)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    incident: Mapped["Incident"] = relationship(
        "Incident", back_populates="report"
    )
