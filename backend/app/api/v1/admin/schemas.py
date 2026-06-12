"""Pydantic I/O schemas for the admin REST API.

All ``Read`` schemas use ``from_attributes=True`` so they can be constructed
directly from SQLAlchemy ORM instances.

All ``Create`` / ``Update`` schemas include field-level validation (min/max
lengths, slug pattern) so invalid input is rejected at the API boundary before
touching the database.

``Update`` schemas use optional fields only; callers send a partial body and
the endpoint applies ``model_dump(exclude_unset=True)`` so absent fields are
never changed.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    default_language: str
    supported_languages: list[str]
    timezone: str
    handoff_settings: dict
    created_at: datetime
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Branches
# ---------------------------------------------------------------------------


class BranchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    slug: str
    name: str
    city: str | None = None
    region: str | None = None
    country: str | None = None
    address: str | None = None
    phone: str | None = None
    timezone: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class BranchCreate(BaseModel):
    slug: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$|^[a-z0-9]$",
        description="URL-safe lowercase slug (letters, digits, hyphens).",
        examples=["dhaka-main", "sylhet-north"],
    )
    name: str = Field(..., min_length=1, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    country: str | None = Field(
        default=None,
        max_length=2,
        description="ISO 3166-1 alpha-2 country code.",
        examples=["BD", "GB"],
    )
    address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(
        default=None,
        max_length=64,
        description="IANA timezone name.",
        examples=["Asia/Dhaka", "Europe/London"],
    )


class BranchUpdate(BaseModel):
    """Partial update — only fields present in the request body are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=2)
    address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(default=None, max_length=64)


# ---------------------------------------------------------------------------
# Knowledge items
# ---------------------------------------------------------------------------

_VALID_KNOWLEDGE_STATUSES = {"draft", "approved", "archived"}


class KnowledgeItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    branch_id: UUID | None = None
    question: str
    answer: str
    language: str
    tags: list[str]
    status: str
    source_type: str
    source_reference: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class KnowledgeItemCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    answer: str = Field(..., min_length=1, max_length=10000)
    language: str = Field(
        default="bn-BD",
        max_length=20,
        description="BCP-47 language tag, e.g. bn-BD, en-US, bn-Latn.",
    )
    branch_id: UUID | None = Field(
        default=None,
        description="Optional branch scope. Null means the item applies to all branches.",
    )
    tags: list[str] = Field(default_factory=list)
    status: str = Field(
        default="draft",
        description="Initial status. One of: draft, approved, archived.",
    )
    source_type: str = Field(default="manual", max_length=50)
    source_reference: str | None = Field(default=None, max_length=500)


class KnowledgeItemUpdate(BaseModel):
    """Partial update — only fields present in the request body are changed."""

    question: str | None = Field(default=None, min_length=1, max_length=2000)
    answer: str | None = Field(default=None, min_length=1, max_length=10000)
    language: str | None = Field(default=None, max_length=20)
    branch_id: UUID | None = None
    tags: list[str] | None = None
    source_reference: str | None = None


class KnowledgeItemStatusResponse(BaseModel):
    """Returned by approve / draft / archive action endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str


class KnowledgeCsvImportErrorRead(BaseModel):
    row_number: int
    field: str
    message: str


class KnowledgeCsvImportResponse(BaseModel):
    imported_count: int
    skipped_count: int
    errors: list[KnowledgeCsvImportErrorRead]
    imported_items: list[KnowledgeItemRead]
