from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.organization import Organization


class ConversationSummary(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "conversation_summaries"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )

    # Overall call outcome classification
    outcome: Mapped[str] = mapped_column(String(30))

    # Counts
    answered_count: Mapped[int] = mapped_column(Integer, default=0)
    unanswered_count: Mapped[int] = mapped_column(Integer, default=0)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    call_duration_seconds: Mapped[int | None] = mapped_column(Integer)

    # Lead fields (denormalised for quick dashboard reads)
    lead_interest: Mapped[str | None] = mapped_column(Text)
    lead_name: Mapped[str | None] = mapped_column(String(255))
    lead_status: Mapped[str | None] = mapped_column(String(30))

    # Handoff
    handoff_reason: Mapped[str | None] = mapped_column(Text)

    # Action flag
    follow_up_needed: Mapped[bool] = mapped_column(Boolean, default=False)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="summary")
    organization: Mapped["Organization"] = relationship(back_populates="summaries")
