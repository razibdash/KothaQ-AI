from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.services.tenancy import OrganizationContext, resolve_organization_by_slug

DatabaseSession = Annotated[Session, Depends(get_db_session)]


def _resolve_request_organization(
    request: Request,
    org_slug: str,
    session: DatabaseSession,
) -> OrganizationContext:
    organization_context = resolve_organization_by_slug(session, org_slug)
    if organization_context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{org_slug}' was not found",
        )

    request.state.organization_context = organization_context
    return organization_context


def get_organization_context(
    request: Request,
    org_slug: str,
    session: DatabaseSession,
) -> OrganizationContext:
    return _resolve_request_organization(request, org_slug, session)


def get_api_organization_context(
    request: Request,
    session: DatabaseSession,
    org_slug: Annotated[str, Header(alias="X-Organization-Slug")],
) -> OrganizationContext:
    return _resolve_request_organization(request, org_slug, session)


ResolvedOrganization = Annotated[
    OrganizationContext,
    Depends(get_organization_context),
]
ResolvedAPIOrganization = Annotated[
    OrganizationContext,
    Depends(get_api_organization_context),
]
