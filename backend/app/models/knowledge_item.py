from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.organization import Organization


class KnowledgeItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_items"
    __table_args__ = (
        Index("ix_knowledge_items_org_status_language", "organization_id", "status", "language"),
        UniqueConstraint(
            "organization_id",
            "source_type",
            "source_reference",
            name="uq_knowledge_items_org_source_reference",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    branch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"),
        index=True,
    )
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(20), default="bn-BD")
    tags: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    source_type: Mapped[str] = mapped_column(String(50), default="manual")
    source_reference: Mapped[str | None] = mapped_column(String(500))
    # Stores a serialised float list produced by the configured embedding model.
    # NULL means the item has not been embedded yet — search falls back to fuzzy.
    question_embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)

    organization: Mapped["Organization"] = relationship(back_populates="knowledge_items")
    branch: Mapped["Branch | None"] = relationship(back_populates="knowledge_items")
