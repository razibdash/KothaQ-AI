"""Admin endpoints — knowledge item CRUD + status transitions (org-scoped)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import DatabaseSession
from app.api.v1.admin.schemas import (
    KnowledgeItemCreate,
    KnowledgeItemRead,
    KnowledgeItemStatusResponse,
    KnowledgeItemUpdate,
    _VALID_KNOWLEDGE_STATUSES,
)
from app.services.storage import TenantStorageService, get_organization_by_slug

router = APIRouter()


def _resolve_storage(session: Session, org_slug: str) -> TenantStorageService:
    org = get_organization_by_slug(session, org_slug)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{org_slug}' not found.",
        )
    return TenantStorageService(session, org.id)


def _get_item_or_404(storage: TenantStorageService, item_id: UUID):
    item = storage.get_knowledge_item(item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge item '{item_id}' not found.",
        )
    return item


@router.get(
    "",
    response_model=list[KnowledgeItemRead],
    summary="List knowledge items",
    description=(
        "Returns all knowledge items for the organization. "
        "Optionally filter by ``status`` (draft, approved, archived)."
    ),
)
def list_knowledge_items(
    org_slug: str,
    session: DatabaseSession,
    item_status: str | None = Query(
        default=None,
        alias="status",
        description="Filter by status: draft, approved, or archived.",
    ),
) -> list[KnowledgeItemRead]:
    storage = _resolve_storage(session, org_slug)
    items = storage.list_knowledge_items()
    if item_status is not None:
        items = [i for i in items if i.status == item_status]
    return [KnowledgeItemRead.model_validate(i) for i in items]


@router.post(
    "",
    response_model=KnowledgeItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create knowledge item",
)
def create_knowledge_item(
    org_slug: str,
    body: KnowledgeItemCreate,
    session: DatabaseSession,
) -> KnowledgeItemRead:
    if body.status not in _VALID_KNOWLEDGE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"status must be one of: {sorted(_VALID_KNOWLEDGE_STATUSES)}",
        )
    storage = _resolve_storage(session, org_slug)
    try:
        item = storage.create_knowledge_item(
            question=body.question,
            answer=body.answer,
            language=body.language,
            branch_id=body.branch_id,
            tags=body.tags,
            status=body.status,
            source_type=body.source_type,
            source_reference=body.source_reference,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return KnowledgeItemRead.model_validate(item)


@router.get(
    "/{item_id}",
    response_model=KnowledgeItemRead,
    summary="Get knowledge item",
)
def get_knowledge_item(
    org_slug: str,
    item_id: UUID,
    session: DatabaseSession,
) -> KnowledgeItemRead:
    storage = _resolve_storage(session, org_slug)
    return KnowledgeItemRead.model_validate(_get_item_or_404(storage, item_id))


@router.patch(
    "/{item_id}",
    response_model=KnowledgeItemRead,
    summary="Update knowledge item",
    description=(
        "Partial update — only fields present in the request body are changed. "
        "Use the dedicated ``/approve``, ``/draft``, and ``/archive`` endpoints "
        "to change status."
    ),
)
def update_knowledge_item(
    org_slug: str,
    item_id: UUID,
    body: KnowledgeItemUpdate,
    session: DatabaseSession,
) -> KnowledgeItemRead:
    storage = _resolve_storage(session, org_slug)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return KnowledgeItemRead.model_validate(_get_item_or_404(storage, item_id))
    # Validate branch scope when branch_id is being changed.
    if "branch_id" in updates and updates["branch_id"] is not None:
        try:
            storage._require_owned_branch(updates["branch_id"])
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
    try:
        item = storage.update_knowledge_item(item_id, updates)
        session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return KnowledgeItemRead.model_validate(item)


# ── Status transition endpoints ───────────────────────────────────────────────


@router.post(
    "/{item_id}/approve",
    response_model=KnowledgeItemStatusResponse,
    summary="Approve knowledge item",
    description=(
        "Mark the item as ``approved`` so it is included in voice-turn semantic "
        "search.  Only approved items are returned to callers."
    ),
)
def approve_knowledge_item(
    org_slug: str,
    item_id: UUID,
    session: DatabaseSession,
) -> KnowledgeItemStatusResponse:
    storage = _resolve_storage(session, org_slug)
    _get_item_or_404(storage, item_id)
    try:
        item = storage.set_knowledge_item_status(item_id, "approved")
        session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return KnowledgeItemStatusResponse.model_validate(item)


@router.post(
    "/{item_id}/draft",
    response_model=KnowledgeItemStatusResponse,
    summary="Revert knowledge item to draft",
    description="Move the item back to ``draft`` status, removing it from active search.",
)
def draft_knowledge_item(
    org_slug: str,
    item_id: UUID,
    session: DatabaseSession,
) -> KnowledgeItemStatusResponse:
    storage = _resolve_storage(session, org_slug)
    _get_item_or_404(storage, item_id)
    try:
        item = storage.set_knowledge_item_status(item_id, "draft")
        session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return KnowledgeItemStatusResponse.model_validate(item)


@router.post(
    "/{item_id}/archive",
    response_model=KnowledgeItemStatusResponse,
    summary="Archive knowledge item",
    description=(
        "Soft-delete the item by setting its status to ``archived``. "
        "Archived items are excluded from search and cannot be returned to callers."
    ),
)
def archive_knowledge_item(
    org_slug: str,
    item_id: UUID,
    session: DatabaseSession,
) -> KnowledgeItemStatusResponse:
    storage = _resolve_storage(session, org_slug)
    _get_item_or_404(storage, item_id)
    try:
        item = storage.set_knowledge_item_status(item_id, "archived")
        session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return KnowledgeItemStatusResponse.model_validate(item)
