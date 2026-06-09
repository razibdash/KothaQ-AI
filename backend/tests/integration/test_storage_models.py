from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.call_turn import CallTurn
from app.models.conversation import Conversation
from app.models.handoff import Handoff
from app.models.knowledge_item import KnowledgeItem
from app.models.lead import Lead
from app.models.organization import Organization
from app.models.phone_number import PhoneNumber
from app.models.unknown_question import UnknownQuestion
from app.services.storage import TenantStorageService, create_organization


def test_create_required_tenant_records(db_session: Session) -> None:
    organization = create_organization(
        db_session,
        slug="demo-university",
        name="Demo University",
        supported_languages=["bn-BD", "bn-Latn", "en-US"],
    )
    storage = TenantStorageService(db_session, organization.id)
    branch = storage.create_branch(
        slug="sylhet",
        name="Sylhet Campus",
        city="Sylhet",
        country="BD",
    )
    phone_number = storage.create_phone_number(
        branch_id=branch.id,
        number_e164="+8802999999999",
        provider="mock",
    )
    faq = storage.create_knowledge_item(
        branch_id=branch.id,
        question="Office time kokhon?",
        answer="Saturday to Thursday, 9 AM to 5 PM.",
        language="bn-Latn",
        tags=["office", "hours"],
        status="approved",
    )
    conversation = storage.create_conversation(
        branch_id=branch.id,
        provider="mock",
        provider_call_id="call-001",
        caller_phone_masked="+8801712345678",
        detected_language="bn-Latn",
    )
    unknown_question = storage.create_unknown_question(
        conversation_id=conversation.id,
        question_text="Is a new scholarship available?",
        normalized_text="new scholarship available",
        detected_language="en-US",
    )
    turn = storage.create_call_turn(
        conversation_id=conversation.id,
        role="assistant",
        output_text="I can connect you to a representative.",
        confidence=0.0,
        intent="unknown_question",
    )
    lead = storage.create_lead(
        conversation_id=conversation.id,
        branch_id=branch.id,
        name="Prospective Student",
        phone_masked="+8801812345678",
        interest="CSE admission",
    )
    handoff = storage.create_handoff(
        conversation_id=conversation.id,
        reason="low_confidence",
        target_number_masked="+8801912345678",
    )
    db_session.commit()

    assert db_session.scalar(select(Organization).where(Organization.id == organization.id))
    assert db_session.scalar(select(Branch).where(Branch.id == branch.id))
    assert db_session.scalar(select(PhoneNumber).where(PhoneNumber.id == phone_number.id))
    assert db_session.scalar(select(KnowledgeItem).where(KnowledgeItem.id == faq.id))
    assert db_session.scalar(select(Conversation).where(Conversation.id == conversation.id))
    assert db_session.scalar(select(CallTurn).where(CallTurn.id == turn.id))
    assert db_session.scalar(
        select(UnknownQuestion).where(UnknownQuestion.id == unknown_question.id)
    )
    assert db_session.scalar(select(Lead).where(Lead.id == lead.id))
    assert db_session.scalar(select(Handoff).where(Handoff.id == handoff.id))
    assert conversation.caller_phone_masked == "*********5678"
    assert lead.phone_masked == "*********5678"
    assert handoff.target_number_masked == "*********5678"


def test_tenant_service_rejects_foreign_branch_and_conversation(
    db_session: Session,
) -> None:
    first_org = create_organization(db_session, slug="first", name="First")
    second_org = create_organization(db_session, slug="second", name="Second")
    first_storage = TenantStorageService(db_session, first_org.id)
    second_storage = TenantStorageService(db_session, second_org.id)
    foreign_branch = first_storage.create_branch(slug="main", name="Main")
    foreign_conversation = first_storage.create_conversation(
        branch_id=foreign_branch.id,
        provider="mock",
        provider_call_id="foreign-call",
    )

    with pytest.raises(ValueError, match="branch does not belong"):
        second_storage.create_knowledge_item(
            branch_id=foreign_branch.id,
            question="Private question",
            answer="Private answer",
            language="en-US",
        )

    with pytest.raises(ValueError, match="conversation does not belong"):
        second_storage.create_unknown_question(
            conversation_id=foreign_conversation.id,
            question_text="Private unknown",
        )


def test_tenant_service_requires_organization_context(db_session: Session) -> None:
    with pytest.raises(ValueError, match="organization_id is required"):
        TenantStorageService(db_session, None)  # type: ignore[arg-type]

    storage = TenantStorageService(db_session, uuid4())
    assert storage.list_knowledge_items() == []
