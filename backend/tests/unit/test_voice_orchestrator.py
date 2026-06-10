import logging
from unittest.mock import Mock
from uuid import UUID

import pytest
from pytest import LogCaptureFixture, MonkeyPatch
from sqlalchemy.orm import Session

from app.core.logging import STRUCTURED_LOG_ATTR
from app.models.knowledge_item import KnowledgeItem
from app.services.knowledge.search import KnowledgeSearchResult
from app.services.voice import orchestrator as orchestrator_module
from app.services.voice.orchestrator import VoiceOrchestrator
from app.services.tenancy import OrganizationContext

ORGANIZATION = OrganizationContext(
    id=UUID("00000000-0000-0000-0000-000000000123"),
    slug="tenant-demo",
    name="Tenant Demo",
    default_language="bn-BD",
    supported_languages=("bn-BD", "bn-Latn", "en-US"),
    timezone="Asia/Dhaka",
)


def structured_events(caplog: LogCaptureFixture) -> list[dict]:
    """Return structured event payloads captured during an orchestrator test."""
    return [
        getattr(record, STRUCTURED_LOG_ATTR)
        for record in caplog.records
        if hasattr(record, STRUCTURED_LOG_ATTR)
    ]


def test_voice_turn_logs_lifecycle_without_transcript(
    caplog: LogCaptureFixture,
    monkeypatch: MonkeyPatch,
) -> None:
    """Log a safe lifecycle and return the localized unknown-answer fallback."""
    caller_text = "My private admission question"
    caplog.set_level(logging.INFO, logger=orchestrator_module.__name__)
    monkeypatch.setattr(
        orchestrator_module,
        "search_knowledge",
        lambda *args, **kwargs: KnowledgeSearchResult.no_verified_answer(),
    )

    response = VoiceOrchestrator(Mock(spec=Session)).handle_turn(
        ORGANIZATION,
        caller_text,
        call_id="call-123",
    )

    events = structured_events(caplog)
    event_names = [event["event"] for event in events]

    assert response
    assert event_names == [
        "user_input_received",
        "language_detected",
        "answer_selected",
        "unknown_question",
        "handoff_requested",
    ]
    assert all(event["tenant_id"] == ORGANIZATION.tenant_id for event in events)
    assert all(event["call_id"] == "call-123" for event in events)
    assert all(event["organization_slug"] == "tenant-demo" for event in events)
    assert caller_text not in caplog.text
    assert events[0]["input_length"] == len(caller_text)
    assert events[1]["language"] == "en-US"
    assert response == (
        "I cannot confirm that yet. "
        "I can connect you with someone who can help."
    )


def test_voice_turn_scopes_knowledge_search_to_resolved_organization(
    monkeypatch: MonkeyPatch,
) -> None:
    """Pass the resolved tenant ID into search and style the verified answer."""
    source_item = Mock(spec=KnowledgeItem)
    source_item.id = UUID("00000000-0000-0000-0000-000000000456")
    source_item.organization_id = ORGANIZATION.id
    source_item.status = "approved"
    source_item.answer = "Verified tenant answer"

    observed_organization_ids: list[UUID] = []

    def scoped_search(
        session: Session,
        organization_id: UUID,
        query: str,
        *,
        branch_id: UUID | None = None,
    ) -> KnowledgeSearchResult:
        """Return a verified result while recording the tenant search scope."""
        observed_organization_ids.append(organization_id)
        return KnowledgeSearchResult(
            answer="Verified tenant answer",
            confidence=0.95,
            source_id=UUID("00000000-0000-0000-0000-000000000456"),
            source_item=source_item,
        )

    monkeypatch.setattr(orchestrator_module, "search_knowledge", scoped_search)

    response = VoiceOrchestrator(Mock(spec=Session)).handle_turn(
        ORGANIZATION,
        "tenant-specific question",
        call_id="call-scoped",
    )

    assert response == "Sure. Verified tenant answer"
    assert observed_organization_ids == [ORGANIZATION.id]


def test_voice_turn_logs_safe_error_context(
    caplog: LogCaptureFixture,
    monkeypatch: MonkeyPatch,
) -> None:
    """Log safe context without exposing exception text or caller input."""
    def fail_search(
        session: Session,
        organization_id: UUID,
        query: str,
        *,
        branch_id: UUID | None = None,
    ) -> KnowledgeSearchResult:
        """Raise a controlled error for safe logging assertions."""
        raise RuntimeError("provider-token-must-not-appear")

    monkeypatch.setattr(orchestrator_module, "search_knowledge", fail_search)
    caplog.set_level(logging.ERROR, logger=orchestrator_module.__name__)

    with pytest.raises(RuntimeError, match="provider-token-must-not-appear"):
        VoiceOrchestrator(Mock(spec=Session)).handle_turn(
            ORGANIZATION,
            "private caller input",
            call_id="call-error",
        )

    error_event = structured_events(caplog)[-1]

    assert error_event == {
        "event": "voice_turn_error",
        "tenant_id": ORGANIZATION.tenant_id,
        "call_id": "call-error",
        "organization_slug": "tenant-demo",
        "error_type": "RuntimeError",
        "operation": "handle_turn",
    }
    assert "provider-token-must-not-appear" not in caplog.text
