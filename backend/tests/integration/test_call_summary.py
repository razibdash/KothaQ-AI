"""Integration tests for deterministic call-summary generation.

Covers:
- Summary auto-generated on complete_conversation().
- On-demand generation via generate_conversation_summary().
- Correct outcome for answered / unknown / handoff / lead scenarios.
- follow_up_needed flag logic.
- Re-generation overwrites the previous summary (upsert).
- API endpoint returns summary or generates on demand.
- Tenant scoping: no cross-org access.
"""

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.analytics.call_summary import summarize_conversation
from app.services.storage import TenantStorageService, create_organization
from app.services.tenancy import OrganizationContext
from app.services.voice.orchestrator import VoiceOrchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _storage(session: Session, org_id: UUID) -> TenantStorageService:
    return TenantStorageService(session, org_id)


def _org_context(org) -> OrganizationContext:
    return OrganizationContext.from_model(org)


# ---------------------------------------------------------------------------
# Auto-generated on complete_conversation
# ---------------------------------------------------------------------------


def test_summary_created_on_complete_conversation(db_session: Session) -> None:
    """complete_conversation() must persist a ConversationSummary automatically."""
    org = create_organization(db_session, slug="sum-auto", name="Sum Auto")
    storage = _storage(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-auto-1")
    db_session.commit()

    storage.complete_conversation(conv.id)
    db_session.commit()

    summary = storage.get_conversation_summary(conv.id)
    assert summary is not None
    assert summary.conversation_id == conv.id
    assert summary.organization_id == org.id
    assert summary.outcome == "no_input"  # no turns were made


def test_summary_records_call_duration(db_session: Session) -> None:
    """call_duration_seconds is computed from started_at and ended_at."""
    org = create_organization(db_session, slug="sum-duration", name="Sum Duration")
    storage = _storage(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-dur-1")
    db_session.commit()

    storage.complete_conversation(conv.id)
    db_session.commit()

    summary = storage.get_conversation_summary(conv.id)
    assert summary is not None
    # Duration should be non-negative (might be 0 in fast test)
    assert summary.call_duration_seconds is not None
    assert summary.call_duration_seconds >= 0


# ---------------------------------------------------------------------------
# On-demand generation
# ---------------------------------------------------------------------------


def test_on_demand_generation_for_existing_conversation(db_session: Session) -> None:
    """generate_conversation_summary() works for conversations not yet completed."""
    org = create_organization(db_session, slug="sum-demand", name="Sum Demand")
    storage = _storage(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-dem-1")
    db_session.commit()

    summary = storage.generate_conversation_summary(conv.id)
    db_session.commit()

    assert summary is not None
    assert summary.conversation_id == conv.id


def test_on_demand_generation_raises_for_unknown_conversation(db_session: Session) -> None:
    from uuid import uuid4

    org = create_organization(db_session, slug="sum-404", name="Sum 404")
    storage = _storage(db_session, org.id)
    db_session.commit()

    with pytest.raises(ValueError):
        storage.generate_conversation_summary(uuid4())


# ---------------------------------------------------------------------------
# Outcome: answered
# ---------------------------------------------------------------------------


def test_summary_outcome_answered_when_kb_match(db_session: Session) -> None:
    """A call where the KB answers every question gets outcome='answered'."""
    org = create_organization(
        db_session,
        slug="sum-answered",
        name="Sum Answered",
        supported_languages=["en-US"],
    )
    storage = _storage(db_session, org.id)
    storage.create_knowledge_item(
        question="What are the office hours?",
        answer="The office is open 9 to 5.",
        language="en-US",
        tags=["office", "hours"],
        status="approved",
    )
    conv = storage.create_conversation(provider="test", provider_call_id="call-ans-1")
    db_session.commit()

    VoiceOrchestrator(db_session).handle_turn(
        _org_context(org),
        "What are the office hours?",
        conversation_id=conv.id,
    )
    db_session.commit()

    storage.create_call_turn(
        conversation_id=conv.id,
        role="user",
        input_text="What are the office hours?",
        output_text="The office is open 9 to 5.",
    )

    result = summarize_conversation(db_session, conv.id, org.id)
    assert result.outcome == "answered"
    assert result.answered_count >= 1
    assert result.unanswered_count == 0
    assert result.follow_up_needed is False


# ---------------------------------------------------------------------------
# Outcome: unknown
# ---------------------------------------------------------------------------


def test_summary_outcome_unknown_when_no_kb_match(db_session: Session) -> None:
    """A call with no KB match and no handoff gets outcome='unknown'."""
    org = create_organization(db_session, slug="sum-unknown", name="Sum Unknown")
    storage = _storage(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-unk-1")

    # Simulate an unknown question being logged
    storage.create_unknown_question(
        question_text="What is the refund policy?",
        conversation_id=conv.id,
        detected_language="en-US",
    )
    # The user turn that triggered it
    storage.create_call_turn(
        conversation_id=conv.id,
        role="user",
        input_text="What is the refund policy?",
        output_text="I cannot verify that information confidently.",
    )
    db_session.commit()

    result = summarize_conversation(db_session, conv.id, org.id)
    assert result.outcome == "unknown"
    assert result.unanswered_count == 1
    assert result.answered_count == 0
    assert result.follow_up_needed is True


# ---------------------------------------------------------------------------
# Outcome: handoff
# ---------------------------------------------------------------------------


def test_summary_outcome_handoff_when_handoff_record_exists(db_session: Session) -> None:
    """Any call with a handoff record must get outcome='handoff'."""
    org = create_organization(db_session, slug="sum-handoff", name="Sum Handoff")
    storage = _storage(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-hof-1")
    db_session.commit()

    storage.create_call_turn(
        conversation_id=conv.id,
        role="user",
        input_text="Transfer me to an agent",
        output_text="Connecting you now.",
    )
    storage.create_handoff(
        conversation_id=conv.id,
        reason="caller_requested",
    )
    db_session.commit()

    result = summarize_conversation(db_session, conv.id, org.id)
    assert result.outcome == "handoff"
    assert result.handoff_reason == "caller_requested"
    assert result.follow_up_needed is True


# ---------------------------------------------------------------------------
# Outcome: lead_captured
# ---------------------------------------------------------------------------


def test_summary_outcome_lead_captured_when_lead_new(db_session: Session) -> None:
    """A call where a lead reached status='new' (complete) gets outcome='lead_captured'."""
    org = create_organization(db_session, slug="sum-lead", name="Sum Lead")
    storage = _storage(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-ld-1")
    db_session.commit()

    lead = storage.create_lead(
        conversation_id=conv.id,
        name="Rahim",
        interest="CSE admission",
        status="new",
    )
    db_session.commit()

    result = summarize_conversation(db_session, conv.id, org.id)
    assert result.outcome == "lead_captured"
    assert result.lead_interest == "CSE admission"
    assert result.lead_name == "Rahim"
    assert result.lead_status == "new"
    assert result.follow_up_needed is True


def test_summary_includes_partial_lead_fields(db_session: Session) -> None:
    """Even a collecting lead is reflected in the summary fields."""
    org = create_organization(db_session, slug="sum-partial-lead", name="Sum Partial Lead")
    storage = _storage(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-pl-1")
    db_session.commit()

    storage.create_lead(
        conversation_id=conv.id,
        interest="MBA program",
        status="collecting",
    )
    db_session.commit()

    result = summarize_conversation(db_session, conv.id, org.id)
    assert result.lead_interest == "MBA program"
    assert result.lead_status == "collecting"
    assert result.follow_up_needed is True
    # Not "lead_captured" because status is still collecting
    assert result.outcome != "lead_captured"


# ---------------------------------------------------------------------------
# Outcome: mixed
# ---------------------------------------------------------------------------


def test_summary_outcome_mixed_when_some_answered_some_unknown(db_session: Session) -> None:
    """A call with both KB answers and unknown questions gets outcome='mixed'."""
    org = create_organization(db_session, slug="sum-mixed", name="Sum Mixed")
    storage = _storage(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-mix-1")
    db_session.commit()

    # Two user turns: one answered (no UQ), one unanswered (creates UQ)
    storage.create_call_turn(
        conversation_id=conv.id,
        role="user",
        input_text="What time does the office open?",
        output_text="The office opens at 9.",
    )
    storage.create_call_turn(
        conversation_id=conv.id,
        role="user",
        input_text="What is the alumni discount?",
        output_text="I cannot verify that information.",
    )
    storage.create_unknown_question(
        question_text="What is the alumni discount?",
        conversation_id=conv.id,
        detected_language="en-US",
    )
    db_session.commit()

    result = summarize_conversation(db_session, conv.id, org.id)
    assert result.outcome == "mixed"
    assert result.answered_count == 1
    assert result.unanswered_count == 1
    assert result.turn_count == 2


# ---------------------------------------------------------------------------
# Upsert: re-generating overwrites
# ---------------------------------------------------------------------------


def test_summary_upsert_overwrites_previous(db_session: Session) -> None:
    """Calling generate_conversation_summary twice replaces, not duplicates, the record."""
    org = create_organization(db_session, slug="sum-upsert", name="Sum Upsert")
    storage = _storage(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-ups-1")
    db_session.commit()

    storage.generate_conversation_summary(conv.id)
    db_session.commit()

    storage.create_unknown_question(
        question_text="Something unanswered",
        conversation_id=conv.id,
        detected_language="en-US",
    )
    db_session.commit()

    storage.generate_conversation_summary(conv.id)
    db_session.commit()

    summaries = db_session.execute(
        __import__("sqlalchemy", fromlist=["select"])
        .select(
            __import__("app.models.conversation_summary", fromlist=["ConversationSummary"])
            .ConversationSummary
        )
        .where(
            __import__("app.models.conversation_summary", fromlist=["ConversationSummary"])
            .ConversationSummary.conversation_id
            == conv.id
        )
    ).scalars().all()

    assert len(summaries) == 1
    assert summaries[0].unanswered_count == 1


# ---------------------------------------------------------------------------
# API endpoint
# ---------------------------------------------------------------------------


def test_api_get_summary_generates_on_demand(
    db_session: Session,
    db_client: TestClient,
) -> None:
    """GET /calls/{id}/summary returns 200 and generates the summary if missing."""
    org = create_organization(db_session, slug="sum-api-gen", name="Sum API Gen")
    storage = _storage(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-api-gen-1")
    db_session.commit()

    response = db_client.get(
        f"/api/v1/calls/{conv.id}/summary",
        headers={"X-Organization-Slug": "sum-api-gen"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == str(conv.id)
    assert body["outcome"] == "no_input"
    assert "follow_up_needed" in body


def test_api_get_summary_returns_cached_summary(
    db_session: Session,
    db_client: TestClient,
) -> None:
    """GET /calls/{id}/summary returns the stored summary without regenerating."""
    org = create_organization(db_session, slug="sum-api-cached", name="Sum API Cached")
    storage = _storage(db_session, org.id)
    conv = storage.create_conversation(provider="test", provider_call_id="call-api-cached-1")
    db_session.commit()

    storage.complete_conversation(conv.id)
    db_session.commit()

    response = db_client.get(
        f"/api/v1/calls/{conv.id}/summary",
        headers={"X-Organization-Slug": "sum-api-cached"},
    )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == str(conv.id)


def test_api_get_summary_returns_404_for_cross_tenant_conversation(
    db_session: Session,
    db_client: TestClient,
) -> None:
    """GET /calls/{id}/summary from a different org returns 404."""
    org_a = create_organization(db_session, slug="sum-cross-a", name="Cross A")
    org_b = create_organization(db_session, slug="sum-cross-b", name="Cross B")
    conv_b = _storage(db_session, org_b.id).create_conversation(
        provider="test", provider_call_id="call-cross-b"
    )
    db_session.commit()

    response = db_client.get(
        f"/api/v1/calls/{conv_b.id}/summary",
        headers={"X-Organization-Slug": "sum-cross-a"},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tenant scoping via summarize_conversation
# ---------------------------------------------------------------------------


def test_summarize_conversation_raises_for_cross_tenant(db_session: Session) -> None:
    """summarize_conversation() raises ValueError if org doesn't own the conversation."""
    org_a = create_organization(db_session, slug="sum-scope-a", name="Scope A")
    org_b = create_organization(db_session, slug="sum-scope-b", name="Scope B")
    conv_b = _storage(db_session, org_b.id).create_conversation(
        provider="test", provider_call_id="call-scope-b"
    )
    db_session.commit()

    with pytest.raises(ValueError, match="not found"):
        summarize_conversation(db_session, conv_b.id, org_a.id)
