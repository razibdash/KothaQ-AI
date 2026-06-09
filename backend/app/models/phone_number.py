from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.organization import Organization


class PhoneNumber(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "phone_numbers"
    __table_args__ = (
        UniqueConstraint("provider", "number_e164", name="uq_phone_numbers_provider_number"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    branch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"),
        index=True,
    )
    number_e164: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(50), default="twilio")
    provider_number_id: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    organization: Mapped["Organization"] = relationship(back_populates="phone_numbers")
    branch: Mapped["Branch | None"] = relationship(back_populates="phone_numbers")
