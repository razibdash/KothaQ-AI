from typing import TYPE_CHECKING

from sqlalchemy import JSON, String
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.conversation import Conversation
    from app.models.handoff import Handoff
    from app.models.knowledge_item import KnowledgeItem
    from app.models.lead import Lead
    from app.models.phone_number import PhoneNumber
    from app.models.unknown_question import UnknownQuestion


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    default_language: Mapped[str] = mapped_column(String(20), default="bn-BD")
    supported_languages: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
    )
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Dhaka")
    handoff_settings: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON),
        default=dict,
    )

    branches: Mapped[list["Branch"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    phone_numbers: Mapped[list["PhoneNumber"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    knowledge_items: Mapped[list["KnowledgeItem"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    unknown_questions: Mapped[list["UnknownQuestion"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    leads: Mapped[list["Lead"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    handoffs: Mapped[list["Handoff"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
