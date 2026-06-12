"""Add question_embedding column to knowledge_items for semantic search.

Stores a serialised float list (JSON array).  NULL = not yet embedded.
The column is intentionally nullable so existing rows are unaffected until
they are re-indexed by the embedding warm-up task or lazy search.

Revision ID: 20260612_0005
Revises: 20260612_0004
Create Date: 2026-06-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260612_0005"
down_revision: str | None = "20260612_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_items",
        sa.Column("question_embedding", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_items", "question_embedding")
