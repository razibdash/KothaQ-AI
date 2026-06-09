"""Add tenant handoff settings and seed reference uniqueness.

Revision ID: 20260609_0002
Revises: 20260609_0001
Create Date: 2026-06-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260609_0002"
down_revision: str | None = "20260609_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "handoff_settings",
                sa.JSON(),
                server_default=sa.text("'{}'"),
                nullable=False,
            )
        )

    with op.batch_alter_table("knowledge_items") as batch_op:
        batch_op.create_unique_constraint(
            "uq_knowledge_items_org_source_reference",
            ["organization_id", "source_type", "source_reference"],
        )


def downgrade() -> None:
    with op.batch_alter_table("knowledge_items") as batch_op:
        batch_op.drop_constraint(
            "uq_knowledge_items_org_source_reference",
            type_="unique",
        )

    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_column("handoff_settings")
