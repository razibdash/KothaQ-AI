"""Integration tests for the unknown-question logging and approval workflow.

Tests verify:
- Unknown questions are persisted when the answer policy denies a turn.
- Approving an unknown question creates a searchable knowledge-base entry.
- Admin API endpoints are scoped to the resolved organization (no cross-tenant leakage).
"""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.knowledge.search import search_knowledge
from app.services.storage import TenantStorageService, create_organization
from app.services.tenancy import OrganizationContext
from app.services.voice.orchestrator import VoiceOrchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _org_context(org) -> OrganizationContext:
    return OrganizationContext.from_model(org)


def _storage(session: Session, org_id: UUID) -> TenantStorageService:
    return TenantStorageService(session, org_id)


# ---------------------------------------------------------------------------
# Unknown question creation via orchestrator
# ---------------------------------------------------------------------------


def test_orchestrator_creates_unknown_question_when_no_kb_match(
    db_session: Session,
) -> None:
    """A voice turn with no KB match must persist an unknown-question record."""
    org = create_organization(db_session, slug="uq-creation", name="UQ Creation")
    db_session.commit()

    VoiceOrchestrator(db_session).handle_turn(
        _org_context(org),
        "What time does the library open?",
        call_id="call-uq-1",
    )
    db_session.commit()

    questions = _storage(db_session, org.id).list_unknown_questions()
    assert len(questions) == 1
    uq = questions[0]
    assert uq.question_text == "What time does the library open?"
    assert uq.status == "new"
    assert uq.organization_id == org.id


def test_orchestrator_does_not_create_unknown_question_when_answer_found(
    db_session: Session,
) -> None:
    """A turn that finds a high-confidence match must NOT create an unknown question."""
    org = create_organization(db_session, slug="uq-no-create", name="UQ No Create")
    storage = _storage(db_session, org.id)
    storage.create_knowledge_item(
        question="What are the office hours?",
        answer="The office is open 9 to 5.",
        language="en-US",
        tags=["office", "hours"],
        status="approved",
    )
    db_session.commit()

    VoiceOrchestrator(db_session).handle_turn(
        _org_context(org),
        "What are the office hours?",
        call_id="call-uq-2",
    )
    db_session.commit()

    questions = storage.list_unknown_questions()
    assert questions == []


def test_orchestrator_links_unknown_question_to_conversation(
    db_session: Session,
) -> None:
    """When conversation_id is provided, the unknown question references it."""
    org = create_organization(db_session, slug="uq-conv", name="UQ Conv")
    storage = _storage(db_session, org.id)
    conv = storage.create_conversation(
        provider="test",
        provider_call_id="call-abc",
    )
    db_session.commit()

    VoiceOrchestrator(db_session).handle_turn(
        _org_context(org),
        "This question has no answer",
        conversation_id=conv.id,
    )
    db_session.commit()

    questions = storage.list_unknown_questions()
    assert len(questions) == 1
    assert questions[0].conversation_id == conv.id


# ---------------------------------------------------------------------------
# Approval into knowledge base
# ---------------------------------------------------------------------------


def test_approve_unknown_question_creates_approved_kb_item(
    db_session: Session,
) -> None:
    """Approving an unknown question must create a status=approved KB entry."""
    org = create_organization(db_session, slug="uq-approve-kb", name="UQ Approve KB")
    storage = _storage(db_session, org.id)
    uq = storage.create_unknown_question(
        question_text="What is the scholarship deadline?",
        detected_language="en-US",
    )
    db_session.commit()

    _uq, kb_item = storage.approve_unknown_question(
        uq.id,
        approved_answer="The scholarship deadline is 30 June.",
        language="en-US",
        tags=["scholarship", "deadline"],
    )
    db_session.commit()

    assert _uq.status == "approved"
    assert _uq.suggested_answer == "The scholarship deadline is 30 June."
    assert kb_item.status == "approved"
    assert kb_item.answer == "The scholarship deadline is 30 June."
    assert kb_item.source_type == "unknown_question_approval"
    assert kb_item.source_reference == str(uq.id)


def test_approved_unknown_answer_is_searchable_in_future_calls(
    db_session: Session,
) -> None:
    """After approval, the same question returns an answer in future voice turns."""
    org = create_organization(db_session, slug="uq-searchable", name="UQ Searchable")
    storage = _storage(db_session, org.id)
    context = _org_context(org)

    # First turn — no KB match, unknown question logged
    VoiceOrchestrator(db_session).handle_turn(context, "Where is the campus located?")
    db_session.commit()

    uq = storage.list_unknown_questions()[0]

    # Admin approves with a verified answer
    storage.approve_unknown_question(
        uq.id,
        approved_answer="The campus is on University Road, Sylhet.",
        language="en-US",
    )
    db_session.commit()

    # Second turn — should now find the KB item
    search_result = search_knowledge(db_session, org.id, "Where is the campus located?")
    assert search_result.answer == "The campus is on University Road, Sylhet."
    assert search_result.confidence >= 0.65


def test_approve_already_approved_question_raises(
    db_session: Session,
) -> None:
    """Approving an already-approved unknown question is rejected."""
    org = create_organization(db_session, slug="uq-double-approve", name="UQ Double")
    storage = _storage(db_session, org.id)
    uq = storage.create_unknown_question(
        question_text="A question",
        detected_language="en-US",
    )
    db_session.commit()

    storage.approve_unknown_question(uq.id, approved_answer="An answer.")
    db_session.commit()

    with pytest.raises(ValueError, match="already approved"):
        storage.approve_unknown_question(uq.id, approved_answer="Another answer.")


# ---------------------------------------------------------------------------
# Admin API — list
# ---------------------------------------------------------------------------


def test_api_list_unknown_questions_scoped_to_org(
    db_session: Session,
    db_client: TestClient,
) -> None:
    """GET /unknown-questions returns only the resolved org's questions."""
    org_a = create_organization(db_session, slug="uq-api-a", name="Org A")
    org_b = create_organization(db_session, slug="uq-api-b", name="Org B")
    _storage(db_session, org_a.id).create_unknown_question(
        question_text="Question from Org A"
    )
    _storage(db_session, org_b.id).create_unknown_question(
        question_text="Question from Org B"
    )
    db_session.commit()

    response = db_client.get(
        "/api/v1/unknown-questions/",
        headers={"X-Organization-Slug": "uq-api-a"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["question_text"] == "Question from Org A"


def test_api_list_filters_by_status(
    db_session: Session,
    db_client: TestClient,
) -> None:
    """GET /unknown-questions?status=new returns only new questions."""
    org = create_organization(db_session, slug="uq-api-filter", name="Filter Org")
    storage = _storage(db_session, org.id)
    storage.create_unknown_question(question_text="New question")
    uq_ignored = storage.create_unknown_question(question_text="Old question")
    db_session.commit()
    storage.mark_unknown_question_ignored(uq_ignored.id)
    db_session.commit()

    response = db_client.get(
        "/api/v1/unknown-questions/?status=new",
        headers={"X-Organization-Slug": "uq-api-filter"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["question_text"] == "New question"


# ---------------------------------------------------------------------------
# Admin API — ignore
# ---------------------------------------------------------------------------


def test_api_ignore_unknown_question(
    db_session: Session,
    db_client: TestClient,
) -> None:
    """PATCH /{id}/ignore sets status to ignored."""
    org = create_organization(db_session, slug="uq-api-ignore", name="Ignore Org")
    uq = _storage(db_session, org.id).create_unknown_question(
        question_text="Ignore this"
    )
    db_session.commit()

    response = db_client.patch(
        f"/api/v1/unknown-questions/{uq.id}/ignore",
        headers={"X-Organization-Slug": "uq-api-ignore"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


def test_api_ignore_returns_404_for_cross_tenant_question(
    db_session: Session,
    db_client: TestClient,
) -> None:
    """PATCH /{id}/ignore from a different org returns 404, not the question."""
    org_a = create_organization(db_session, slug="uq-cross-a", name="Cross A")
    org_b = create_organization(db_session, slug="uq-cross-b", name="Cross B")
    uq = _storage(db_session, org_b.id).create_unknown_question(
        question_text="Org B question"
    )
    db_session.commit()

    response = db_client.patch(
        f"/api/v1/unknown-questions/{uq.id}/ignore",
        headers={"X-Organization-Slug": "uq-cross-a"},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Admin API — approve
# ---------------------------------------------------------------------------


def test_api_approve_creates_kb_item_and_returns_ids(
    db_session: Session,
    db_client: TestClient,
) -> None:
    """POST /{id}/approve creates a KB entry and returns both IDs."""
    org = create_organization(db_session, slug="uq-api-approve", name="Approve Org")
    uq = _storage(db_session, org.id).create_unknown_question(
        question_text="What documents are needed?",
        detected_language="en-US",
    )
    db_session.commit()

    response = db_client.post(
        f"/api/v1/unknown-questions/{uq.id}/approve",
        json={"answer": "Bring your SSC certificate and NID.", "language": "en-US"},
        headers={"X-Organization-Slug": "uq-api-approve"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert UUID(body["unknown_question_id"]) == uq.id
    assert "knowledge_item_id" in body

    # Verify KB item is searchable
    kb_id = UUID(body["knowledge_item_id"])
    result = search_knowledge(db_session, org.id, "What documents are needed?")
    assert result.source_id == kb_id
    assert result.answer == "Bring your SSC certificate and NID."


def test_api_approve_returns_409_when_already_approved(
    db_session: Session,
    db_client: TestClient,
) -> None:
    """POST /{id}/approve on an already-approved question returns 409."""
    org = create_organization(db_session, slug="uq-api-dup", name="Dup Org")
    storage = _storage(db_session, org.id)
    uq = storage.create_unknown_question(
        question_text="A question", detected_language="en-US"
    )
    db_session.commit()
    storage.approve_unknown_question(uq.id, approved_answer="First answer.")
    db_session.commit()

    response = db_client.post(
        f"/api/v1/unknown-questions/{uq.id}/approve",
        json={"answer": "Second answer."},
        headers={"X-Organization-Slug": "uq-api-dup"},
    )

    assert response.status_code == 409


def test_api_approve_returns_404_for_cross_tenant_question(
    db_session: Session,
    db_client: TestClient,
) -> None:
    """POST /{id}/approve from a different org returns 404."""
    org_a = create_organization(db_session, slug="uq-ap-cross-a", name="Cross A")
    org_b = create_organization(db_session, slug="uq-ap-cross-b", name="Cross B")
    uq = _storage(db_session, org_b.id).create_unknown_question(
        question_text="Org B question"
    )
    db_session.commit()

    response = db_client.post(
        f"/api/v1/unknown-questions/{uq.id}/approve",
        json={"answer": "Some answer."},
        headers={"X-Organization-Slug": "uq-ap-cross-a"},
    )

    assert response.status_code == 404
