from sqlalchemy.orm import Session

from app.services.storage import TenantStorageService, create_organization
from app.services.tenancy import (
    resolve_organization_by_phone_number,
    resolve_organization_by_slug,
)


def test_resolver_uses_exact_slug_and_phone_mapping(db_session: Session) -> None:
    first = create_organization(db_session, slug="first", name="First")
    second = create_organization(db_session, slug="second", name="Second")
    TenantStorageService(db_session, second.id).create_phone_number(
        number_e164="+8802999999999",
        provider="mock",
    )
    db_session.commit()

    slug_context = resolve_organization_by_slug(db_session, "first")
    phone_context = resolve_organization_by_phone_number(
        db_session,
        "+8802999999999",
        "mock",
    )

    assert slug_context is not None
    assert slug_context.id == first.id
    assert phone_context is not None
    assert phone_context.id == second.id
    assert resolve_organization_by_slug(db_session, "missing") is None
