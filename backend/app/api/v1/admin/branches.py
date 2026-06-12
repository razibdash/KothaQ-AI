"""Admin endpoints — branch CRUD (organization-scoped)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import DatabaseSession
from app.api.v1.admin.schemas import BranchCreate, BranchRead, BranchUpdate
from app.services.storage import TenantStorageService, get_organization_by_slug

router = APIRouter()


def _resolve_storage(session: Session, org_slug: str) -> TenantStorageService:
    """Resolve org by slug and return a tenant-scoped storage service."""
    org = get_organization_by_slug(session, org_slug)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{org_slug}' not found.",
        )
    return TenantStorageService(session, org.id)


@router.get(
    "",
    response_model=list[BranchRead],
    summary="List branches",
    description="Returns all branches for the specified organization, ordered by name.",
)
def list_branches(org_slug: str, session: DatabaseSession) -> list[BranchRead]:
    storage = _resolve_storage(session, org_slug)
    return [BranchRead.model_validate(b) for b in storage.list_branches()]


@router.post(
    "",
    response_model=BranchRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create branch",
)
def create_branch(
    org_slug: str,
    body: BranchCreate,
    session: DatabaseSession,
) -> BranchRead:
    storage = _resolve_storage(session, org_slug)
    try:
        branch = storage.create_branch(
            slug=body.slug,
            name=body.name,
            city=body.city,
            region=body.region,
            country=body.country,
            address=body.address,
            phone=body.phone,
            timezone=body.timezone,
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return BranchRead.model_validate(branch)


@router.get(
    "/{branch_id}",
    response_model=BranchRead,
    summary="Get branch",
)
def get_branch(org_slug: str, branch_id: UUID, session: DatabaseSession) -> BranchRead:
    storage = _resolve_storage(session, org_slug)
    branch = storage.get_branch(branch_id)
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Branch '{branch_id}' not found in organization '{org_slug}'.",
        )
    return BranchRead.model_validate(branch)


@router.patch(
    "/{branch_id}",
    response_model=BranchRead,
    summary="Update branch",
    description=(
        "Partial update — only fields present in the request body are changed. "
        "Absent fields are left unchanged."
    ),
)
def update_branch(
    org_slug: str,
    branch_id: UUID,
    body: BranchUpdate,
    session: DatabaseSession,
) -> BranchRead:
    storage = _resolve_storage(session, org_slug)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        # No fields supplied — return current state without touching the DB.
        branch = storage.get_branch(branch_id)
        if branch is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found.")
        return BranchRead.model_validate(branch)
    try:
        branch = storage.update_branch(branch_id, updates)
        session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return BranchRead.model_validate(branch)
