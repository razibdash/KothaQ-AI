from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.call_turn import CallTurn
    from app.models.conversation_summary import ConversationSummary
    from app.models.handoff import Handoff
    from app.models.lead import Lead
    from app.models.organization import Organization
    from app.models.unknown_question import UnknownQuestion


class Conversation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_call_id",
            name="uq_conversations_provider_call_id",
        ),
        Index("ix_conversations_org_started_at", "organization_id", "started_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    branch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"),
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50))
    provider_call_id: Mapped[str] = mapped_column(String(255))
    caller_phone_masked: Mapped[str | None] = mapped_column(String(32))
    detected_language: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="started")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization: Mapped["Organization"] = relationship(back_populates="conversations")
    branch: Mapped["Branch | None"] = relationship(back_populates="conversations")
    turns: Mapped[list["CallTurn"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    unknown_questions: Mapped[list["UnknownQuestion"]] = relationship(
        back_populates="conversation",
    )
    leads: Mapped[list["Lead"]] = relationship(back_populates="conversation")
    handoffs: Mapped[list["Handoff"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    summary: Mapped["ConversationSummary | None"] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        uselist=False,
    )
