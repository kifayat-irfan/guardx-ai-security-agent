"""Phase 7: incidents + incident_reports tables.

Revision ID: 20261007_0003
Revises: 20261007_0002
Create Date: 2026-10-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261007_0003"
down_revision: Union[str, None] = "20261007_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_event_id", sa.String(64), nullable=False),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("zone_name", sa.String(200), nullable=False),
        sa.Column("tracking_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("detection_confidence", sa.Float(), nullable=False),
        sa.Column("bounding_box", sa.JSON(), nullable=False),
        sa.Column("point", sa.JSON(), nullable=False),
        sa.Column("event_data", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("recommended_action", sa.Text(), nullable=True),
        sa.Column("analysis_confidence", sa.Float(), nullable=True),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("workflow_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id"),
    )
    op.create_table(
        "incident_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True),
                  nullable=False),
        sa.Column("report_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(16), nullable=True),
        sa.Column("recommended_action", sa.Text(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("cited_policy_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("retrieved_policy_count", sa.Integer(), nullable=False),
        sa.Column("retrieved_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_id"),
    )
    # useful indexes (not over-indexed)
    for table, col in (
        ("incidents", "external_event_id"),
        ("incidents", "camera_id"),
        ("incidents", "zone_id"),
        ("incidents", "zone_name"),
        ("incidents", "event_type"),
        ("incidents", "occurred_at"),
        ("incidents", "status"),
        ("incidents", "severity"),
        ("incidents", "workflow_id"),
        ("incident_reports", "incident_id"),
    ):
        op.create_index(f"ix_{table}_{col}", table, [col])


def downgrade() -> None:
    op.drop_table("incident_reports")
    op.drop_table("incidents")
