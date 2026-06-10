"""Integration tests for Twilio-compatible voice webhook endpoints.

Covers:
- Incoming call greeting
- Gather with answer found
- Gather with unknown answer (handoff)
- Gather with empty speech result
- Explicit human-handoff request from caller
- Handoff endpoint
- Invalid organisation slug (404)
"""

import xml.etree.ElementTree as ET
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.knowledge.search import KnowledgeSearchResult
from app.services.storage import create_organization
from app.services.voice import orchestrator as orchestrator_module

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ORG_SLUG = "voice-test-org"
_CALL_SID = "CA000000000000000000000000000001"
_CALLER = "+15555550101"


def _parse(response_text: str) -> ET.Element:
    """Parse TwiML XML response and return the root <Response> element."""
    return ET.fromstring(response_text)


def _tags(root: ET.Element) -> list[str]:
    return [child.tag for child in root]


def _make_approved_item(organization_id: UUID, answer: str) -> Mock:
    item = Mock(spec=["id", "organization_id", "status", "answer"])
    item.id = UUID("00000000-0000-0000-0000-aaaaaaaaaaaa")
    item.organization_id = organization_id
    item.status = "approved"
    item.answer = answer
    return item


def _setup_org(
    db_session: Session,
    *,
    handoff_phone: str | None = None,
) -> object:
    hs = {"phone_number": handoff_phone} if handoff_phone else {}
    org = create_organization(
        db_session,
        slug=_ORG_SLUG,
        name="Voice Test Org",
        default_language="en-US",
        supported_languages=["en-US"],
        handoff_settings=hs,
    )
    db_session.commit()
    return org


# ---------------------------------------------------------------------------
# Incoming call
# ---------------------------------------------------------------------------


def test_incoming_call_returns_greeting_twiml(
    db_client: TestClient,
    db_session: Session,
) -> None:
    """POST /voice/incoming/{org_slug} returns 200 with TwiML greeting and Gather."""
    _setup_org(db_session)

    response = db_client.post(
        f"/api/v1/voice/incoming/{_ORG_SLUG}",
        data={"CallSid": _CALL_SID, "From": _CALLER},
    )

    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]

    root = _parse(response.text)
    assert root.tag == "Response"
    child_tags = _tags(root)
    assert "Say" in child_tags
    assert "Gather" in child_tags

    gather = root.find("Gather")
    assert gather is not None
    assert gather.attrib["input"] == "speech"
    assert gather.attrib["method"] == "POST"
    assert "/voice/gather/" in gather.attrib["action"]


# ---------------------------------------------------------------------------
# Gather — answer found
# ---------------------------------------------------------------------------


def test_gather_answer_found_returns_answer_twiml(
    db_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gather with a high-confidence knowledge answer returns the answer + follow-up Gather."""
    org = _setup_org(db_session)
    source_item = _make_approved_item(org.id, "Admission opens every January.")

    monkeypatch.setattr(
        orchestrator_module,
        "search_knowledge",
        lambda *a, **kw: KnowledgeSearchResult(
            answer="Admission opens every January.",
            confidence=0.95,
            source_id=source_item.id,
            source_item=source_item,
        ),
    )

    response = db_client.post(
        f"/api/v1/voice/gather/{_ORG_SLUG}",
        data={"CallSid": _CALL_SID, "From": _CALLER, "SpeechResult": "When is admission?"},
    )

    assert response.status_code == 200
    root = _parse(response.text)
    assert root.tag == "Response"

    # First child should be <Say> with the answer text
    first_say = root.find("Say")
    assert first_say is not None
    assert "Admission opens every January." in (first_say.text or "")

    # Should include a follow-up Gather
    gather = root.find("Gather")
    assert gather is not None
    assert "/voice/gather/" in gather.attrib["action"]


# ---------------------------------------------------------------------------
# Gather — unknown answer → handoff
# ---------------------------------------------------------------------------


def test_gather_unknown_answer_returns_handoff_twiml(
    db_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gather with no matching knowledge returns handoff TwiML."""
    _setup_org(db_session, handoff_phone="+15559998888")

    monkeypatch.setattr(
        orchestrator_module,
        "search_knowledge",
        lambda *a, **kw: KnowledgeSearchResult.no_verified_answer(),
    )

    response = db_client.post(
        f"/api/v1/voice/gather/{_ORG_SLUG}",
        data={"CallSid": _CALL_SID, "From": _CALLER, "SpeechResult": "Something unknown"},
    )

    assert response.status_code == 200
    root = _parse(response.text)
    # Handoff TwiML contains a <Say> (hold message) and <Dial>
    assert root.find("Dial") is not None
    dial = root.find("Dial")
    assert dial is not None and dial.text == "+15559998888"


# ---------------------------------------------------------------------------
# Gather — empty speech result
# ---------------------------------------------------------------------------


def test_gather_empty_speech_returns_retry_twiml(
    db_client: TestClient,
    db_session: Session,
) -> None:
    """Gather called with no SpeechResult returns retry TwiML (Gather without Dial)."""
    _setup_org(db_session)

    response = db_client.post(
        f"/api/v1/voice/gather/{_ORG_SLUG}",
        data={"CallSid": _CALL_SID, "From": _CALLER},
    )

    assert response.status_code == 200
    root = _parse(response.text)
    assert root.find("Gather") is not None
    assert root.find("Dial") is None


# ---------------------------------------------------------------------------
# Gather — explicit handoff request
# ---------------------------------------------------------------------------


def test_gather_explicit_handoff_keyword_transfers_caller(
    db_client: TestClient,
    db_session: Session,
) -> None:
    """Caller saying 'human' bypasses knowledge pipeline and returns handoff TwiML."""
    _setup_org(db_session, handoff_phone="+15557776666")

    response = db_client.post(
        f"/api/v1/voice/gather/{_ORG_SLUG}",
        data={"CallSid": _CALL_SID, "From": _CALLER, "SpeechResult": "Talk to a human please"},
    )

    assert response.status_code == 200
    root = _parse(response.text)
    dial = root.find("Dial")
    assert dial is not None and dial.text == "+15557776666"


def test_gather_handoff_without_phone_plays_apology(
    db_client: TestClient,
    db_session: Session,
) -> None:
    """Handoff with no configured phone number returns an apology <Say>, no <Dial>."""
    _setup_org(db_session)  # no handoff_phone

    response = db_client.post(
        f"/api/v1/voice/gather/{_ORG_SLUG}",
        data={"CallSid": _CALL_SID, "From": _CALLER, "SpeechResult": "I want an agent"},
    )

    assert response.status_code == 200
    root = _parse(response.text)
    assert root.find("Dial") is None
    assert root.find("Say") is not None


# ---------------------------------------------------------------------------
# Handoff endpoint
# ---------------------------------------------------------------------------


def test_handoff_endpoint_dials_configured_number(
    db_client: TestClient,
    db_session: Session,
) -> None:
    """POST /voice/handoff/{org_slug} returns <Dial> TwiML when phone is configured."""
    _setup_org(db_session, handoff_phone="+15554443333")

    response = db_client.post(
        f"/api/v1/voice/handoff/{_ORG_SLUG}",
        data={"CallSid": _CALL_SID, "From": _CALLER},
    )

    assert response.status_code == 200
    root = _parse(response.text)
    dial = root.find("Dial")
    assert dial is not None and dial.text == "+15554443333"


def test_handoff_endpoint_without_phone_plays_apology(
    db_client: TestClient,
    db_session: Session,
) -> None:
    """POST /voice/handoff/{org_slug} without a configured number returns <Say> apology."""
    _setup_org(db_session)

    response = db_client.post(
        f"/api/v1/voice/handoff/{_ORG_SLUG}",
        data={"CallSid": _CALL_SID, "From": _CALLER},
    )

    assert response.status_code == 200
    root = _parse(response.text)
    assert root.find("Dial") is None
    assert root.find("Say") is not None


# ---------------------------------------------------------------------------
# Conversation and turn logging
# ---------------------------------------------------------------------------


def test_incoming_call_creates_conversation_and_turn(
    db_client: TestClient,
    db_session: Session,
) -> None:
    """Incoming call persists a Conversation and an assistant greeting turn."""
    from app.models.call_turn import CallTurn
    from app.models.conversation import Conversation
    from sqlalchemy import select

    org = _setup_org(db_session)

    db_client.post(
        f"/api/v1/voice/incoming/{_ORG_SLUG}",
        data={"CallSid": _CALL_SID, "From": _CALLER},
    )

    conv = db_session.scalar(
        select(Conversation).where(
            Conversation.organization_id == org.id,
            Conversation.provider == "twilio",
            Conversation.provider_call_id == _CALL_SID,
        )
    )
    assert conv is not None

    turns = db_session.scalars(
        select(CallTurn).where(CallTurn.conversation_id == conv.id)
    ).all()
    assert len(turns) == 1
    assert turns[0].role == "assistant"


def test_gather_logs_unknown_question(
    db_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gather with no matching answer creates an UnknownQuestion record."""
    from app.models.unknown_question import UnknownQuestion
    from sqlalchemy import select

    org = _setup_org(db_session)

    monkeypatch.setattr(
        orchestrator_module,
        "search_knowledge",
        lambda *a, **kw: KnowledgeSearchResult.no_verified_answer(),
    )

    db_client.post(
        f"/api/v1/voice/gather/{_ORG_SLUG}",
        data={"CallSid": _CALL_SID, "From": _CALLER, "SpeechResult": "An unanswerable question"},
    )

    uqs = db_session.scalars(
        select(UnknownQuestion).where(UnknownQuestion.organization_id == org.id)
    ).all()
    assert len(uqs) == 1
    assert uqs[0].question_text == "An unanswerable question"


# ---------------------------------------------------------------------------
# Invalid organisation
# ---------------------------------------------------------------------------


def test_invalid_org_slug_returns_404(db_client: TestClient) -> None:
    """Requests to a non-existent org_slug are rejected with HTTP 404."""
    for endpoint in ("incoming", "gather", "handoff"):
        response = db_client.post(
            f"/api/v1/voice/{endpoint}/no-such-org",
            data={"CallSid": _CALL_SID, "From": _CALLER},
        )
        assert response.status_code == 404, f"Expected 404 for /voice/{endpoint}/no-such-org"
