"""Add conversation_summaries table for deterministic post-call summaries.

Revision ID: 20260612_0004
Revises: 20260611_0003
Create Date: 2026-06-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260612_0004"
down_revision: str | None = "20260611_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_summaries",
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("answered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unanswered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("call_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("lead_interest", sa.Text(), nullable=True),
        sa.Column("lead_name", sa.String(length=255), nullable=True),
        sa.Column("lead_status", sa.String(length=30), nullable=True),
        sa.Column("handoff_reason", sa.Text(), nullable=True),
        sa.Column("follow_up_needed", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_conversation_summaries_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_conversation_summaries_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation_summaries")),
        sa.UniqueConstraint(
            "conversation_id",
            name=op.f("uq_conversation_summaries_conversation_id"),
        ),
    )
    op.create_index(
        op.f("ix_conversation_summaries_conversation_id"),
        "conversation_summaries",
        ["conversation_id"],
    )
    op.create_index(
        op.f("ix_conversation_summaries_organization_id"),
        "conversation_summaries",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_conversation_summaries_organization_id"),
        table_name="conversation_summaries",
    )
    op.drop_index(
        op.f("ix_conversation_summaries_conversation_id"),
        table_name="conversation_summaries",
    )
    op.drop_table("conversation_summaries")
