"""Integration tests for the lead capture engine.

Tests verify:
- Lead intent detection triggers lead creation.
- Lead fields accumulate incrementally across turns.
- Lead is linked to the correct organization and conversation.
- FAQ answering and lead capture can co-exist in the same call.
- No lead is created for general FAQ-only queries.
- Lead lifecycle progresses: collecting → finalizing → new.
"""

from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.services.storage import TenantStorageService, create_organization
from app.services.tenancy import OrganizationContext
from app.services.voice.orchestrator import VoiceOrchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _org_context(org) -> OrganizationContext:
    return OrganizationContext.from_model(org)


def _leads(session: Session, org_id: UUID) -> list[Lead]:
    return list(
        session.scalars(
            select(Lead).where(Lead.organization_id == org_id)
        )
    )


# ---------------------------------------------------------------------------
# Lead created on intent detection
# ---------------------------------------------------------------------------


def test_lead_created_when_admission_intent_detected(db_session: Session) -> None:
    """An admission utterance with a conversation_id creates a collecting lead."""
    org = create_organization(db_session, slug="lead-create", name="Lead Create Org")
    storage = TenantStorageService(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-lc-1")
    db_session.commit()

    VoiceOrchestrator(db_session).handle_turn(
        _org_context(org),
        "I want to apply for CSE admission",
        conversation_id=conv.id,
    )
    db_session.commit()

    leads = _leads(db_session, org.id)
    assert len(leads) == 1
    lead = leads[0]
    assert lead.organization_id == org.id
    assert lead.conversation_id == conv.id
    assert lead.status == "collecting"
    assert lead.interest is not None


def test_no_lead_created_for_general_faq_query(db_session: Session) -> None:
    """A generic FAQ question with no lead intent must not create a lead."""
    org = create_organization(db_session, slug="lead-no-create", name="Lead No Create")
    storage = TenantStorageService(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-lnc-1")
    db_session.commit()

    VoiceOrchestrator(db_session).handle_turn(
        _org_context(org),
        "What time does the office open?",
        conversation_id=conv.id,
    )
    db_session.commit()

    assert _leads(db_session, org.id) == []


def test_no_lead_when_no_conversation_id(db_session: Session) -> None:
    """Calls without a conversation_id skip lead capture entirely."""
    org = create_organization(db_session, slug="lead-no-conv", name="Lead No Conv")
    db_session.commit()

    VoiceOrchestrator(db_session).handle_turn(
        _org_context(org),
        "I want admission information",
    )
    db_session.commit()

    assert _leads(db_session, org.id) == []


# ---------------------------------------------------------------------------
# Lead fields accumulate across turns
# ---------------------------------------------------------------------------


def test_lead_captures_interest_from_first_turn(db_session: Session) -> None:
    org = create_organization(db_session, slug="lead-interest", name="Lead Interest")
    storage = TenantStorageService(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-li-1")
    db_session.commit()

    VoiceOrchestrator(db_session).handle_turn(
        _org_context(org),
        "I want to apply for MBA admission",
        conversation_id=conv.id,
    )
    db_session.commit()

    lead = _leads(db_session, org.id)[0]
    assert lead.interest is not None
    assert "MBA" in lead.interest or lead.interest == "admission"


def test_lead_captures_name_from_subsequent_turn(db_session: Session) -> None:
    """Turn 1 triggers lead creation; turn 2 with caller's name captures it."""
    org = create_organization(db_session, slug="lead-name", name="Lead Name")
    storage = TenantStorageService(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-ln-1")
    db_session.commit()

    orch = VoiceOrchestrator(db_session)

    orch.handle_turn(
        _org_context(org),
        "I want to apply for admission",
        conversation_id=conv.id,
    )
    db_session.commit()

    # Turn 2: caller gives their name (no lead intent keyword, but active lead exists)
    orch.handle_turn(
        _org_context(org),
        "my name is Rahim",
        conversation_id=conv.id,
    )
    db_session.commit()

    lead = _leads(db_session, org.id)[0]
    assert lead.name == "Rahim"


def test_existing_field_not_overwritten_in_later_turn(db_session: Session) -> None:
    """Once interest is stored, a later turn cannot overwrite it."""
    org = create_organization(db_session, slug="lead-no-overwrite", name="Lead No Overwrite")
    storage = TenantStorageService(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-low-1")
    db_session.commit()

    orch = VoiceOrchestrator(db_session)
    orch.handle_turn(
        _org_context(org),
        "I want to apply for CSE admission",
        conversation_id=conv.id,
    )
    db_session.commit()

    first_interest = _leads(db_session, org.id)[0].interest

    orch.handle_turn(
        _org_context(org),
        "actually I want MBA admission",
        conversation_id=conv.id,
    )
    db_session.commit()

    lead = _leads(db_session, org.id)[0]
    assert lead.interest == first_interest


# ---------------------------------------------------------------------------
# Lead lifecycle: collecting → finalizing → new
# ---------------------------------------------------------------------------


def test_lead_transitions_to_finalizing_when_mandatory_fields_complete(
    db_session: Session,
) -> None:
    """When interest + name are captured the lead moves to 'finalizing'."""
    org = create_organization(db_session, slug="lead-finalizing", name="Lead Finalizing")
    storage = TenantStorageService(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-lf-1")
    db_session.commit()

    orch = VoiceOrchestrator(db_session)
    orch.handle_turn(
        _org_context(org),
        "I want to apply for CSE admission",
        conversation_id=conv.id,
    )
    db_session.commit()

    orch.handle_turn(
        _org_context(org),
        "my name is Rahim",
        conversation_id=conv.id,
    )
    db_session.commit()

    lead = _leads(db_session, org.id)[0]
    assert lead.status == "finalizing"


def test_lead_finalized_with_callback_notes_on_third_turn(db_session: Session) -> None:
    """After finalizing, the next turn extracts callback_notes and closes the lead."""
    org = create_organization(db_session, slug="lead-final-cb", name="Lead Final CB")
    storage = TenantStorageService(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-fcb-1")
    db_session.commit()

    orch = VoiceOrchestrator(db_session)
    orch.handle_turn(
        _org_context(org),
        "I want to apply for admission",
        conversation_id=conv.id,
    )
    db_session.commit()

    orch.handle_turn(
        _org_context(org),
        "my name is Sarah",
        conversation_id=conv.id,
    )
    db_session.commit()

    orch.handle_turn(
        _org_context(org),
        "please call me tomorrow morning",
        conversation_id=conv.id,
    )
    db_session.commit()

    lead = _leads(db_session, org.id)[0]
    assert lead.status == "new"
    assert lead.callback_notes is not None
    assert "tomorrow" in lead.callback_notes.lower()


def test_lead_finalized_immediately_when_all_fields_in_one_utterance(
    db_session: Session,
) -> None:
    """If name + callback given together, lead goes directly to 'new' in two turns."""
    org = create_organization(db_session, slug="lead-instant", name="Lead Instant")
    storage = TenantStorageService(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-li2-1")
    db_session.commit()

    orch = VoiceOrchestrator(db_session)
    orch.handle_turn(
        _org_context(org),
        "I want to apply for CSE admission",
        conversation_id=conv.id,
    )
    db_session.commit()

    # Name + callback time in same utterance
    orch.handle_turn(
        _org_context(org),
        "my name is John, call me tomorrow afternoon",
        conversation_id=conv.id,
    )
    db_session.commit()

    lead = _leads(db_session, org.id)[0]
    assert lead.status == "new"
    assert lead.name == "John"
    assert lead.callback_notes is not None


# ---------------------------------------------------------------------------
# FAQ and lead capture co-exist in the same call
# ---------------------------------------------------------------------------


def test_faq_answer_and_lead_question_in_same_response(db_session: Session) -> None:
    """When a KB match exists, the response contains both the answer and a lead question."""
    org = create_organization(
        db_session,
        slug="lead-faq-combo",
        name="Lead FAQ Combo",
        supported_languages=["en-US"],
    )
    storage = TenantStorageService(db_session, org.id)
    storage.create_knowledge_item(
        question="What is the CSE admission fee?",
        answer="The CSE admission fee is 5000 BDT.",
        language="en-US",
        tags=["cse", "admission", "fee"],
        status="approved",
    )
    conv = storage.create_conversation(provider="test", provider_call_id="call-faq-combo-1")
    db_session.commit()

    result = VoiceOrchestrator(db_session).handle_turn(
        _org_context(org),
        "What is the CSE admission fee?",
        conversation_id=conv.id,
    )
    db_session.commit()

    # Response must contain the KB answer
    assert "5000" in result.response_text
    # Response must also contain a lead follow-up question
    assert "?" in result.response_text
    # A collecting lead must have been created
    leads = _leads(db_session, org.id)
    assert len(leads) == 1
    assert leads[0].status == "collecting"


# ---------------------------------------------------------------------------
# Tenancy: lead is scoped to the correct organization
# ---------------------------------------------------------------------------


def test_lead_is_scoped_to_resolved_organization(db_session: Session) -> None:
    """Leads for org A are never visible to org B."""
    org_a = create_organization(db_session, slug="lead-scope-a", name="Org A")
    org_b = create_organization(db_session, slug="lead-scope-b", name="Org B")
    storage_a = TenantStorageService(db_session, org_a.id)
    conv_a = storage_a.create_conversation(provider="test", provider_call_id="call-scope-a")
    db_session.commit()

    VoiceOrchestrator(db_session).handle_turn(
        _org_context(org_a),
        "I want to apply for admission",
        conversation_id=conv_a.id,
    )
    db_session.commit()

    assert len(_leads(db_session, org_a.id)) == 1
    assert len(_leads(db_session, org_b.id)) == 0


# ---------------------------------------------------------------------------
# No lead created when handoff policy triggers
# ---------------------------------------------------------------------------


def test_no_lead_question_appended_when_handoff_triggered(db_session: Session) -> None:
    """When the answer policy triggers a handoff, lead questions are suppressed."""
    org = create_organization(
        db_session,
        slug="lead-handoff",
        name="Lead Handoff",
        supported_languages=["en-US"],
    )
    storage = TenantStorageService(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-lh-1")
    db_session.commit()

    # Low-confidence / no-KB turn triggers handoff
    result = VoiceOrchestrator(db_session).handle_turn(
        _org_context(org),
        "I want to apply but also what is the refund policy?",
        conversation_id=conv.id,
    )
    db_session.commit()

    assert result.should_handoff is True
    # Lead question must NOT be appended to a handoff response
    assert "Which program" not in result.response_text
    assert "May I have your name" not in result.response_text
