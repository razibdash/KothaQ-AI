from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.knowledge_item import KnowledgeItem
from app.models.organization import Organization
from app.seeds.demo import DEMO_TENANTS, seed_demo_tenants


def test_demo_seed_is_idempotent(db_session: Session) -> None:
    first_summary = seed_demo_tenants(db_session)
    db_session.commit()
    first_ids = set(db_session.scalars(select(KnowledgeItem.id)))

    second_summary = seed_demo_tenants(db_session)
    db_session.commit()
    second_ids = set(db_session.scalars(select(KnowledgeItem.id)))

    assert first_summary.organizations_created == 3
    assert first_summary.branches_created == 3
    assert first_summary.knowledge_items_created == 60
    assert second_summary.organizations_created == 0
    assert second_summary.branches_created == 0
    assert second_summary.knowledge_items_created == 0
    assert second_summary.organizations_updated == 3
    assert second_summary.branches_updated == 3
    assert second_summary.knowledge_items_updated == 60
    assert first_ids == second_ids
    assert db_session.scalar(select(func.count()).select_from(Organization)) == 3
    assert db_session.scalar(select(func.count()).select_from(Branch)) == 3
    assert db_session.scalar(select(func.count()).select_from(KnowledgeItem)) == 60


def test_demo_seed_has_language_handoff_and_required_faq_topics(
    db_session: Session,
) -> None:
    seed_demo_tenants(db_session)
    db_session.commit()

    required_keys_by_tenant = {
        "demo-university-sylhet": {
            "cse-cost",
            "admission-fee",
            "admission-documents",
            "scholarship",
            "waiver",
            "office-hours",
            "location",
            "contact",
            "callback",
            "program-list",
            "application-deadline",
            "payment-method",
        },
        "demo-school-sylhet": {
            "admission-fee",
            "admission-documents",
            "scholarship",
            "waiver",
            "office-hours",
            "location",
            "contact",
            "callback",
            "program-list",
            "application-deadline",
            "payment-method",
        },
        "demo-service-company": {
            "service-cost",
            "booking-fee",
            "required-documents",
            "discount",
            "office-hours",
            "location",
            "contact",
            "callback",
            "service-list",
            "application-deadline",
            "payment-method",
        },
    }

    for tenant_seed in DEMO_TENANTS:
        organization = db_session.scalar(
            select(Organization).where(Organization.slug == tenant_seed.slug)
        )
        assert organization is not None
        assert organization.default_language == tenant_seed.default_language
        assert organization.supported_languages == list(tenant_seed.supported_languages)
        assert organization.handoff_settings == {
            "enabled": True,
            "mode": "mock",
            "fallback_number_masked": tenant_seed.handoff_number_masked,
        }

        items = list(
            db_session.scalars(
                select(KnowledgeItem).where(
                    KnowledgeItem.organization_id == organization.id,
                    KnowledgeItem.source_type == "demo_seed",
                )
            )
        )
        seeded_keys = {
            item.source_reference.removeprefix(f"{tenant_seed.slug}:")
            for item in items
            if item.source_reference
        }

        assert len(items) == 20
        assert all(item.status == "approved" for item in items)
        assert required_keys_by_tenant[tenant_seed.slug] <= seeded_keys

        deadline = next(
            item
            for item in items
            if (item.source_reference or "").endswith(":application-deadline")
        )
        payment = next(
            item
            for item in items
            if (item.source_reference or "").endswith(":payment-method")
        )
        assert "placeholder" in deadline.answer.lower()
        assert "verified" in payment.answer.lower()

    university = db_session.scalar(
        select(Organization).where(Organization.slug == "demo-university-sylhet")
    )
    assert university is not None
    university_keys = set(
        db_session.scalars(
            select(KnowledgeItem.source_reference).where(
                KnowledgeItem.organization_id == university.id
            )
        )
    )
    assert "demo-university-sylhet:cse-cost" in university_keys
    assert "demo-university-sylhet:admission-fee" in university_keys
