from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.knowledge_item import KnowledgeItem
    from app.models.lead import Lead
    from app.models.organization import Organization
    from app.models.phone_number import PhoneNumber


class Branch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_branches_organization_slug"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    slug: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(2))
    address: Mapped[str | None] = mapped_column(String(500))
    phone: Mapped[str | None] = mapped_column(String(32))
    timezone: Mapped[str | None] = mapped_column(String(64))

    organization: Mapped["Organization"] = relationship(back_populates="branches")
    phone_numbers: Mapped[list["PhoneNumber"]] = relationship(back_populates="branch")
    knowledge_items: Mapped[list["KnowledgeItem"]] = relationship(back_populates="branch")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="branch")
    leads: Mapped[list["Lead"]] = relationship(back_populates="branch")
