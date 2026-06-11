from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.conversation import Conversation
    from app.models.organization import Organization


class Lead(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (Index("ix_leads_org_status", "organization_id", "status"),)

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        index=True,
    )
    name: Mapped[str | None] = mapped_column(String(255))
    phone_masked: Mapped[str | None] = mapped_column(String(32))
    interest: Mapped[str | None] = mapped_column(Text)
    branch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"),
        index=True,
    )
    callback_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    callback_notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="new")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    organization: Mapped["Organization"] = relationship(back_populates="leads")
    conversation: Mapped["Conversation | None"] = relationship(back_populates="leads")
    branch: Mapped["Branch | None"] = relationship(back_populates="leads")
