"""Admin endpoints — organization list and detail."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import DatabaseSession
from app.api.v1.admin.schemas import OrganizationRead
from app.services.storage import get_organization_by_slug, list_organizations

router = APIRouter()


@router.get(
    "",
    response_model=list[OrganizationRead],
    summary="List all organizations",
    description="Returns every organization in the system, ordered by name.",
)
def list_orgs(session: DatabaseSession) -> list[OrganizationRead]:
    return [OrganizationRead.model_validate(o) for o in list_organizations(session)]


@router.get(
    "/{org_slug}",
    response_model=OrganizationRead,
    summary="Get organization by slug",
)
def get_org(org_slug: str, session: DatabaseSession) -> OrganizationRead:
    org = get_organization_by_slug(session, org_slug)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{org_slug}' not found.",
        )
    return OrganizationRead.model_validate(org)
