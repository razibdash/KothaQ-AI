from sqlalchemy.orm import Session

from app.services.knowledge.search import search_knowledge
from app.services.storage import TenantStorageService, create_organization


def test_search_never_returns_another_organizations_knowledge(
    db_session: Session,
) -> None:
    first_org = create_organization(db_session, slug="first-org", name="First Org")
    second_org = create_organization(db_session, slug="second-org", name="Second Org")
    first_storage = TenantStorageService(db_session, first_org.id)
    second_storage = TenantStorageService(db_session, second_org.id)
    first_item = first_storage.create_knowledge_item(
        question="What are the office hours?",
        answer="First organization office answer.",
        language="en-US",
        tags=["office", "hours"],
        status="approved",
    )
    second_item = second_storage.create_knowledge_item(
        question="What is the private CSE admission fee?",
        answer="Second organization private fee answer.",
        language="en-US",
        tags=["cse", "admission", "fees"],
        status="approved",
    )
    db_session.commit()

    first_result = search_knowledge(
        db_session,
        first_org.id,
        "private CSE admission fee",
    )
    second_result = search_knowledge(
        db_session,
        second_org.id,
        "private CSE admission fee",
    )

    assert first_result.answer is None
    assert first_result.source_id is None
    assert second_result.answer == second_item.answer
    assert second_result.source_id == second_item.id
    assert second_result.source_id != first_item.id


def test_search_returns_only_approved_items_and_rejects_low_confidence(
    db_session: Session,
) -> None:
    organization = create_organization(db_session, slug="approved-only", name="Approved")
    storage = TenantStorageService(db_session, organization.id)
    storage.create_knowledge_item(
        question="What is the secret draft scholarship?",
        answer="This draft must never be caller-facing.",
        language="en-US",
        tags=["scholarship"],
        status="draft",
    )
    storage.create_knowledge_item(
        question="What are the office hours?",
        answer="The office is open during published business hours.",
        language="en-US",
        tags=["office", "hours"],
        status="approved",
    )
    db_session.commit()

    draft_result = search_knowledge(
        db_session,
        organization.id,
        "secret draft scholarship",
    )
    unrelated_result = search_knowledge(
        db_session,
        organization.id,
        "weather forecast tomorrow",
    )

    assert draft_result.answer is None
    assert draft_result.source_id is None
    assert unrelated_result.answer is None
    assert unrelated_result.source_id is None
    assert unrelated_result.confidence < 0.65


def test_search_supports_english_bangla_banglish_and_basic_fuzzy_queries(
    db_session: Session,
    monkeypatch,
) -> None:
    # This test exercises the deterministic fuzzy-search path.
    # Force semantic search off so the assertions (based on token overlap) hold
    # regardless of which embedding model is installed.
    import app.services.ai.embeddings as emb_mod
    monkeypatch.setattr(emb_mod, "is_semantic_available", lambda: False)
    organization = create_organization(
        db_session,
        slug="multilingual",
        name="Multilingual Organization",
    )
    storage = TenantStorageService(db_session, organization.id)
    documents = storage.create_knowledge_item(
        question="Which documents are needed for admission?",
        answer="Bring certificates and identification.",
        language="en-US",
        tags=["admission", "documents"],
        status="approved",
    )
    admission_fee = storage.create_knowledge_item(
        question="What is the admission fee?",
        answer="Request the current official admission fee schedule.",
        language="en-US",
        tags=["admission", "fees"],
        status="approved",
    )
    cse_fee = storage.create_knowledge_item(
        question="CSE cost koto?",
        answer="Request the current official CSE fee schedule.",
        language="bn-Latn",
        tags=["cse", "fees"],
        status="approved",
    )
    office = storage.create_knowledge_item(
        question="অফিস সময় কখন?",
        answer="অফিস ৯টা থেকে ৫টা।",
        language="bn-BD",
        tags=["অফিস", "সময়"],
        status="approved",
    )
    closing_time = storage.create_knowledge_item(
        question="What time does the office close?",
        answer="The office closes at the published closing time.",
        language="en-US",
        tags=["office", "hours", "closing"],
        status="approved",
    )
    db_session.commit()

    english_result = search_knowledge(
        db_session,
        organization.id,
        "admisson documents",
    )
    banglish_result = search_knowledge(
        db_session,
        organization.id,
        "CSE fee koto",
    )
    banglish_documents_result = search_knowledge(
        db_session,
        organization.id,
        "admission er jonno ki ki lagbe",
    )
    sylhet_result = search_knowledge(
        db_session,
        organization.id,
        "afne admissionor lagi kita lagbo",
    )
    bangla_result = search_knowledge(
        db_session,
        organization.id,
        "ভর্তি ফি কত",
    )
    bangla_office_result = search_knowledge(
        db_session,
        organization.id,
        "অফিস কখন",
    )
    banglish_office_result = search_knowledge(
        db_session,
        organization.id,
        "office koytay bondho",
    )

    assert english_result.source_id == documents.id
    assert english_result.confidence >= 0.65
    assert banglish_result.source_id == cse_fee.id
    assert banglish_result.confidence >= 0.65
    assert banglish_documents_result.source_id == documents.id
    assert banglish_documents_result.confidence >= 0.65
    assert sylhet_result.source_id == documents.id
    assert sylhet_result.confidence >= 0.65
    assert bangla_result.source_id == admission_fee.id
    assert bangla_result.confidence >= 0.65
    assert bangla_office_result.source_id == office.id
    assert banglish_office_result.source_id == closing_time.id
    assert banglish_office_result.confidence >= 0.65


def test_search_honors_optional_branch_scope(db_session: Session) -> None:
    organization = create_organization(db_session, slug="branches", name="Branches")
    other_organization = create_organization(
        db_session,
        slug="other-branches",
        name="Other Branches",
    )
    storage = TenantStorageService(db_session, organization.id)
    other_storage = TenantStorageService(db_session, other_organization.id)
    sylhet = storage.create_branch(slug="sylhet", name="Sylhet")
    dhaka = storage.create_branch(slug="dhaka", name="Dhaka")
    foreign_branch = other_storage.create_branch(slug="foreign", name="Foreign")
    global_item = storage.create_knowledge_item(
        question="How can I request a callback?",
        answer="Leave your preferred callback time.",
        language="en-US",
        tags=["callback"],
        status="approved",
    )
    sylhet_item = storage.create_knowledge_item(
        branch_id=sylhet.id,
        question="Where is the Sylhet branch?",
        answer="Sylhet branch answer.",
        language="en-US",
        tags=["location", "sylhet"],
        status="approved",
    )
    storage.create_knowledge_item(
        branch_id=dhaka.id,
        question="Where is the Dhaka branch?",
        answer="Dhaka branch answer.",
        language="en-US",
        tags=["location", "dhaka"],
        status="approved",
    )
    db_session.commit()

    sylhet_result = search_knowledge(
        db_session,
        organization.id,
        "Sylhet branch location",
        branch_id=sylhet.id,
    )
    hidden_dhaka_result = search_knowledge(
        db_session,
        organization.id,
        "Dhaka branch location",
        branch_id=sylhet.id,
    )
    global_result = search_knowledge(
        db_session,
        organization.id,
        "request callback",
        branch_id=sylhet.id,
    )
    foreign_branch_result = search_knowledge(
        db_session,
        organization.id,
        "request callback",
        branch_id=foreign_branch.id,
    )

    assert sylhet_result.source_id == sylhet_item.id
    assert hidden_dhaka_result.answer is None
    assert global_result.source_id == global_item.id
    assert foreign_branch_result.answer is None
    assert foreign_branch_result.source_id is None
