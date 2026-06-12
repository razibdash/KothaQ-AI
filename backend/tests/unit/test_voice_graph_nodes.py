"""Unit tests for individual LangGraph node functions in the voice orchestrator.

Each node function accepts a VoiceTurnState dict and returns a partial dict.
Tests construct the minimal required state, call the node directly, and assert
on the returned output dict — no LangGraph runtime is required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.models.knowledge_item import KnowledgeItem
from app.services.ai.answer_policy import AnswerPolicyResult
from app.services.knowledge.search import KnowledgeSearchResult
from app.services.tenancy import OrganizationContext
from app.services.voice.orchestrator import (
    VoiceTurnState,
    _node_capture_lead,
    _node_detect_language,
    _node_log_and_finalize,
    _node_search_and_evaluate,
    _node_style_response,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

ORG = OrganizationContext(
    id=UUID("00000000-0000-0000-0000-000000000001"),
    slug="test-org",
    name="Test Org",
    default_language="en-US",
    supported_languages=("en-US", "bn-BD"),
    timezone="Asia/Dhaka",
)


def _base_state(**overrides) -> VoiceTurnState:
    state: dict = {
        "session": Mock(spec=Session),
        "organization": ORG,
        "caller_text": "What are the office hours?",
        "call_id": "call-test",
        "branch_id": None,
        "conversation_id": None,
        "response_style": "student_friendly",
    }
    state.update(overrides)
    return state  # type: ignore[return-value]


def _policy(
    *,
    allowed: bool = True,
    confidence: float = 0.95,
    should_handoff: bool = False,
    should_log_unknown: bool = False,
    response_text: str = "Office is open 9–5.",
    reason: str = "high_confidence_approved",
    source_id: UUID | None = None,
) -> AnswerPolicyResult:
    return AnswerPolicyResult(
        answer_allowed=allowed,
        response_text=response_text,
        confidence=confidence,
        reason=reason,
        source_knowledge_item_id=source_id,
        should_handoff=should_handoff,
        should_log_unknown=should_log_unknown,
    )


# ---------------------------------------------------------------------------
# _node_detect_language
# ---------------------------------------------------------------------------


class TestNodeDetectLanguage:
    def test_english_text_resolves_to_en_us(self) -> None:
        state = _base_state(caller_text="What are the admission fees?")
        out = _node_detect_language(state)
        assert out["detected_language"] == "en-US"

    def test_bangla_text_resolves_to_bn_bd(self) -> None:
        state = _base_state(
            caller_text="ভর্তি ফি কত?",
            organization=OrganizationContext(
                id=ORG.id,
                slug=ORG.slug,
                name=ORG.name,
                default_language="bn-BD",
                supported_languages=("bn-BD", "en-US"),
                timezone=ORG.timezone,
            ),
        )
        out = _node_detect_language(state)
        assert out["detected_language"] == "bn-BD"

    def test_returns_only_detected_language_key(self) -> None:
        out = _node_detect_language(_base_state())
        assert set(out.keys()) == {"detected_language"}


# ---------------------------------------------------------------------------
# _node_search_and_evaluate
# ---------------------------------------------------------------------------


class TestNodeSearchAndEvaluate:
    def test_high_confidence_result_sets_should_handoff_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app.services.voice.orchestrator as mod

        source_item = Mock(spec=KnowledgeItem)
        source_item.id = UUID("00000000-0000-0000-0000-000000000002")
        source_item.organization_id = ORG.id
        source_item.status = "approved"
        source_item.answer = "Office is open 9-5."

        monkeypatch.setattr(
            mod,
            "search_knowledge",
            lambda *a, **kw: KnowledgeSearchResult(
                answer="Office is open 9-5.",
                confidence=0.95,
                source_id=source_item.id,
                source_item=source_item,
            ),
        )

        state = {**_base_state(), "detected_language": "en-US"}
        out = _node_search_and_evaluate(state)  # type: ignore[arg-type]

        assert out["should_handoff"] is False
        assert out["policy"].answer_allowed is True
        assert out["policy"].confidence == 0.95
        assert "search_result" in out
        assert "normalized_text" in out

    def test_no_knowledge_result_triggers_handoff(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app.services.voice.orchestrator as mod

        monkeypatch.setattr(
            mod,
            "search_knowledge",
            lambda *a, **kw: KnowledgeSearchResult.no_verified_answer(),
        )

        state = {**_base_state(), "detected_language": "en-US"}
        out = _node_search_and_evaluate(state)  # type: ignore[arg-type]

        assert out["should_handoff"] is True
        assert out["policy"].answer_allowed is False

    def test_cross_tenant_result_is_denied(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app.services.voice.orchestrator as mod

        other_org_item = Mock(spec=KnowledgeItem)
        other_org_item.id = UUID("00000000-0000-0000-0000-000000000099")
        other_org_item.organization_id = UUID("00000000-0000-0000-0000-000000000099")
        other_org_item.status = "approved"

        monkeypatch.setattr(
            mod,
            "search_knowledge",
            lambda *a, **kw: KnowledgeSearchResult(
                answer="Leaked answer",
                confidence=0.99,
                source_id=other_org_item.id,
                source_item=other_org_item,
            ),
        )

        state = {**_base_state(), "detected_language": "en-US"}
        out = _node_search_and_evaluate(state)  # type: ignore[arg-type]

        assert out["policy"].answer_allowed is False
        assert out["policy"].reason == "cross_tenant_source"


# ---------------------------------------------------------------------------
# _node_style_response
# ---------------------------------------------------------------------------


class TestNodeStyleResponse:
    def test_allowed_answer_is_styled(self) -> None:
        state = {
            **_base_state(),
            "detected_language": "en-US",
            "policy": _policy(allowed=True, response_text="Office hours are 9 to 5."),
        }
        out = _node_style_response(state)  # type: ignore[arg-type]
        assert "9 to 5" in out["response_text"]
        assert "Sure." in out["response_text"]

    def test_denied_answer_returns_fallback(self) -> None:
        state = {
            **_base_state(),
            "detected_language": "en-US",
            "policy": _policy(allowed=False, should_handoff=True),
        }
        out = _node_style_response(state)  # type: ignore[arg-type]
        # unknown_answer_fallback for en / student_friendly
        assert "connect you with someone" in out["response_text"]

    def test_bangla_fallback_is_in_bangla(self) -> None:
        state = {
            **_base_state(),
            "detected_language": "bn-BD",
            "policy": _policy(allowed=False, should_handoff=True),
        }
        out = _node_style_response(state)  # type: ignore[arg-type]
        assert "প্রতিনিধি" in out["response_text"]

    def test_returns_only_response_text_key(self) -> None:
        state = {
            **_base_state(),
            "detected_language": "en-US",
            "policy": _policy(),
        }
        out = _node_style_response(state)  # type: ignore[arg-type]
        assert set(out.keys()) == {"response_text"}


# ---------------------------------------------------------------------------
# _node_capture_lead
# ---------------------------------------------------------------------------


class TestNodeCaptureLead:
    def test_no_conversation_id_is_noop(self) -> None:
        state = {
            **_base_state(conversation_id=None),
            "detected_language": "en-US",
            "policy": _policy(),
            "response_text": "Sure. Office is open 9-5.",
        }
        out = _node_capture_lead(state)  # type: ignore[arg-type]
        assert out == {"lead_follow_up": None}

    def test_no_intent_in_text_is_noop_when_no_active_lead(self) -> None:
        session_mock = Mock(spec=Session)
        storage_mock = MagicMock()
        storage_mock.get_active_lead.return_value = None

        with patch(
            "app.services.voice.orchestrator.TenantStorageService",
            return_value=storage_mock,
        ):
            state = {
                **_base_state(
                    session=session_mock,
                    caller_text="What are the opening times?",
                    conversation_id=UUID("00000000-0000-0000-0000-000000000010"),
                ),
                "detected_language": "en-US",
                "policy": _policy(),
                "response_text": "9 to 5.",
            }
            out = _node_capture_lead(state)  # type: ignore[arg-type]

        assert out == {"lead_follow_up": None}
        storage_mock.get_active_lead.assert_called_once()

    def test_admission_intent_triggers_lead_question(self) -> None:
        session_mock = Mock(spec=Session)
        storage_mock = MagicMock()
        storage_mock.get_active_lead.return_value = None
        mock_lead = MagicMock()
        mock_lead.id = UUID("00000000-0000-0000-0000-000000000011")
        storage_mock.upsert_collecting_lead.return_value = mock_lead

        with patch(
            "app.services.voice.orchestrator.TenantStorageService",
            return_value=storage_mock,
        ):
            state = {
                **_base_state(
                    session=session_mock,
                    caller_text="I want to apply for admission",
                    conversation_id=UUID("00000000-0000-0000-0000-000000000010"),
                ),
                "detected_language": "en-US",
                "policy": _policy(should_handoff=False),
                "response_text": "Sure.",
            }
            out = _node_capture_lead(state)  # type: ignore[arg-type]

        # Should ask for name (next mandatory field after interest is captured)
        assert out["lead_follow_up"] is not None
        assert isinstance(out["lead_follow_up"], str)


# ---------------------------------------------------------------------------
# _node_log_and_finalize
# ---------------------------------------------------------------------------


class TestNodeLogAndFinalize:
    def test_lead_follow_up_is_appended_to_response(self) -> None:
        state = {
            **_base_state(),
            "detected_language": "en-US",
            "policy": _policy(),
            "response_text": "Office hours are 9 to 5.",
            "lead_follow_up": "May I have your name please?",
            "normalized_text": "office hours",
            "should_handoff": False,
        }
        out = _node_log_and_finalize(state)  # type: ignore[arg-type]
        assert out["response_text"] == "Office hours are 9 to 5. May I have your name please?"

    def test_no_follow_up_leaves_response_unchanged(self) -> None:
        state = {
            **_base_state(),
            "detected_language": "en-US",
            "policy": _policy(),
            "response_text": "Office hours are 9 to 5.",
            "lead_follow_up": None,
            "normalized_text": "office hours",
            "should_handoff": False,
        }
        out = _node_log_and_finalize(state)  # type: ignore[arg-type]
        assert out["response_text"] == "Office hours are 9 to 5."

    def test_unknown_question_logged_when_policy_requests_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        storage_mock = MagicMock()
        session_mock = Mock(spec=Session)

        with patch(
            "app.services.voice.orchestrator.TenantStorageService",
            return_value=storage_mock,
        ):
            state = {
                **_base_state(session=session_mock),
                "detected_language": "en-US",
                "policy": _policy(
                    allowed=False,
                    should_handoff=True,
                    should_log_unknown=True,
                    reason="low_confidence",
                ),
                "response_text": "I cannot confirm that.",
                "lead_follow_up": None,
                "normalized_text": "unknown question text",
                "should_handoff": True,
            }
            _node_log_and_finalize(state)  # type: ignore[arg-type]

        storage_mock.create_unknown_question.assert_called_once()
