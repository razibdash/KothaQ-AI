from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.phone_number import PhoneNumber


@dataclass(frozen=True)
class OrganizationContext:
    id: UUID
    slug: str
    name: str
    default_language: str
    supported_languages: tuple[str, ...]
    timezone: str
    handoff_settings: dict[str, object] = field(default_factory=dict)

    @property
    def tenant_id(self) -> str:
        return str(self.id)

    @classmethod
    def from_model(cls, organization: Organization) -> "OrganizationContext":
        return cls(
            id=organization.id,
            slug=organization.slug,
            name=organization.name,
            default_language=organization.default_language,
            supported_languages=tuple(organization.supported_languages),
            timezone=organization.timezone,
            handoff_settings=dict(organization.handoff_settings),
        )


def resolve_organization_by_slug(
    session: Session,
    org_slug: str,
) -> OrganizationContext | None:
    organization = session.scalar(
        select(Organization).where(Organization.slug == org_slug)
    )
    if organization is None:
        return None
    return OrganizationContext.from_model(organization)


def resolve_organization_by_phone_number(
    session: Session,
    number_e164: str,
    provider: str,
) -> OrganizationContext | None:
    organization = session.scalar(
        select(Organization)
        .join(PhoneNumber)
        .where(
            PhoneNumber.number_e164 == number_e164,
            PhoneNumber.provider == provider,
            PhoneNumber.is_active.is_(True),
        )
    )
    if organization is None:
        return None
    return OrganizationContext.from_model(organization)
