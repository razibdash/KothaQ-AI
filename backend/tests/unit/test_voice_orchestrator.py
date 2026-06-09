import logging

import pytest
from pytest import LogCaptureFixture, MonkeyPatch

from app.core.logging import STRUCTURED_LOG_ATTR
from app.services.voice import orchestrator as orchestrator_module
from app.services.voice.orchestrator import VoiceOrchestrator


def structured_events(caplog: LogCaptureFixture) -> list[dict]:
    return [
        getattr(record, STRUCTURED_LOG_ATTR)
        for record in caplog.records
        if hasattr(record, STRUCTURED_LOG_ATTR)
    ]


def test_voice_turn_logs_lifecycle_without_transcript(caplog: LogCaptureFixture) -> None:
    caller_text = "My private admission question"
    caplog.set_level(logging.INFO, logger=orchestrator_module.__name__)

    response = VoiceOrchestrator().handle_turn(
        "tenant-demo",
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
    assert all(event["tenant_id"] == "tenant-demo" for event in events)
    assert all(event["call_id"] == "call-123" for event in events)
    assert caller_text not in caplog.text
    assert events[0]["input_length"] == len(caller_text)


def test_voice_turn_logs_safe_error_context(
    caplog: LogCaptureFixture,
    monkeypatch: MonkeyPatch,
) -> None:
    def fail_search(organization_id: str, query: str) -> dict:
        raise RuntimeError("provider-token-must-not-appear")

    monkeypatch.setattr(orchestrator_module, "search_knowledge", fail_search)
    caplog.set_level(logging.ERROR, logger=orchestrator_module.__name__)

    with pytest.raises(RuntimeError, match="provider-token-must-not-appear"):
        VoiceOrchestrator().handle_turn(
            "tenant-demo",
            "private caller input",
            call_id="call-error",
        )

    error_event = structured_events(caplog)[-1]

    assert error_event == {
        "event": "voice_turn_error",
        "tenant_id": "tenant-demo",
        "call_id": "call-error",
        "error_type": "RuntimeError",
        "operation": "handle_turn",
    }
    assert "provider-token-must-not-appear" not in caplog.text
