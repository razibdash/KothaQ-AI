from unittest.mock import Mock
from uuid import UUID

import pytest

from app.models.knowledge_item import KnowledgeItem
from app.services.ai.answer_policy import (
    HIGH_CONFIDENCE_THRESHOLD,
    MEDIUM_CONFIDENCE_THRESHOLD,
    AnswerPolicyCandidate,
    evaluate_answer_policy,
)

ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
ITEM_ID = UUID("00000000-0000-0000-0000-000000000002")
OTHER_ORG_ID = UUID("00000000-0000-0000-0000-000000000099")


def _item(
    *,
    org_id: UUID = ORG_ID,
    item_id: UUID = ITEM_ID,
    status: str = "approved",
    answer: str = "The office is open from 9 to 5.",
) -> Mock:
    """Build a minimal KnowledgeItem mock sufficient for policy evaluation."""
    mock = Mock(spec=KnowledgeItem)
    mock.id = item_id
    mock.organization_id = org_id
    mock.status = status
    mock.answer = answer
    return mock


def _candidate(item: Mock | None, confidence: float) -> AnswerPolicyCandidate:
    return AnswerPolicyCandidate(item=item, confidence=confidence)


# ---------------------------------------------------------------------------
# High confidence
# ---------------------------------------------------------------------------


def test_high_confidence_approved_answer_is_allowed() -> None:
    """A high-confidence approved item is returned verbatim without a hedge."""
    result = evaluate_answer_policy(
        "office hours",
        "office hours time",
        ORG_ID,
        _candidate(_item(answer="Office hours are 9 to 5."), HIGH_CONFIDENCE_THRESHOLD),
    )

    assert result.answer_allowed is True
    assert result.response_text == "Office hours are 9 to 5."
    assert result.reason == "high_confidence_approved"
    assert result.source_knowledge_item_id == ITEM_ID
    assert result.should_handoff is False
    assert result.should_log_unknown is False


def test_high_confidence_sensitive_approved_answer_is_allowed() -> None:
    """Sensitive topics are answered at high confidence when source is approved."""
    result = evaluate_answer_policy(
        "fee koto",
        "fee cost tuition",
        ORG_ID,
        _candidate(_item(answer="Tuition fee is 5,000 BDT."), 0.90),
    )

    assert result.answer_allowed is True
    assert result.response_text == "Tuition fee is 5,000 BDT."
    assert result.reason == "high_confidence_approved"


# ---------------------------------------------------------------------------
# Medium confidence
# ---------------------------------------------------------------------------


def test_medium_confidence_non_sensitive_answer_carries_hedge() -> None:
    """Medium-confidence non-sensitive answers are prefixed with a hedge."""
    result = evaluate_answer_policy(
        "where is the office",
        "office location address",
        ORG_ID,
        _candidate(_item(answer="The office is near the main gate."), 0.72),
    )

    assert result.answer_allowed is True
    assert result.response_text.startswith("Based on available information: ")
    assert "The office is near the main gate." in result.response_text
    assert result.reason == "medium_confidence_approved"
    assert result.should_handoff is False


def test_medium_confidence_sensitive_topic_is_denied() -> None:
    """Sensitive topics at medium confidence are denied regardless of approval."""
    result = evaluate_answer_policy(
        "fee koto",
        "fee cost tuition",
        ORG_ID,
        _candidate(_item(answer="Fee is 5,000 BDT."), 0.72),
    )

    assert result.answer_allowed is False
    assert result.reason == "sensitive_topic_medium_confidence"
    assert result.should_handoff is True
    assert result.should_log_unknown is False
    assert result.source_knowledge_item_id == ITEM_ID


# ---------------------------------------------------------------------------
# Low confidence
# ---------------------------------------------------------------------------


def test_low_confidence_triggers_handoff_and_log() -> None:
    """Low confidence triggers handoff and unknown-question logging."""
    result = evaluate_answer_policy(
        "random question",
        "random question",
        ORG_ID,
        _candidate(_item(), MEDIUM_CONFIDENCE_THRESHOLD - 0.01),
    )

    assert result.answer_allowed is False
    assert result.reason == "low_confidence"
    assert result.should_handoff is True
    assert result.should_log_unknown is True
    assert result.source_knowledge_item_id is None


@pytest.mark.parametrize("confidence", [0.0, 0.30, 0.64])
def test_any_sub_threshold_confidence_is_low(confidence: float) -> None:
    result = evaluate_answer_policy(
        "question",
        "question",
        ORG_ID,
        _candidate(_item(), confidence),
    )
    assert result.answer_allowed is False
    assert result.reason == "low_confidence"


# ---------------------------------------------------------------------------
# Unknown question (no candidate)
# ---------------------------------------------------------------------------


def test_no_candidate_triggers_handoff_and_log() -> None:
    """A missing candidate is treated as an unknown question."""
    result = evaluate_answer_policy(
        "something we have no data on",
        "something we have no data on",
        ORG_ID,
        _candidate(None, 0.0),
    )

    assert result.answer_allowed is False
    assert result.reason == "no_candidate"
    assert result.should_handoff is True
    assert result.should_log_unknown is True
    assert result.source_knowledge_item_id is None


# ---------------------------------------------------------------------------
# Cross-tenant
# ---------------------------------------------------------------------------


def test_cross_tenant_item_is_denied_with_zero_confidence() -> None:
    """An item from a different organization is always rejected."""
    foreign_item = _item(org_id=OTHER_ORG_ID)
    result = evaluate_answer_policy(
        "any question",
        "any question",
        ORG_ID,
        _candidate(foreign_item, 0.95),
    )

    assert result.answer_allowed is False
    assert result.reason == "cross_tenant_source"
    assert result.confidence == 0.0
    assert result.should_handoff is True
    assert result.should_log_unknown is False


def test_cross_tenant_check_precedes_confidence_check() -> None:
    """Cross-tenant denial is issued before low-confidence denial."""
    foreign_item = _item(org_id=OTHER_ORG_ID)
    result = evaluate_answer_policy(
        "any question",
        "any question",
        ORG_ID,
        _candidate(foreign_item, 0.10),
    )

    assert result.reason == "cross_tenant_source"


# ---------------------------------------------------------------------------
# Sensitive topic — unapproved source
# ---------------------------------------------------------------------------


def test_sensitive_topic_with_unapproved_source_is_denied() -> None:
    """A sensitive query against a draft item must be denied."""
    draft_item = _item(status="draft")
    result = evaluate_answer_policy(
        "fee koto",
        "fee cost tuition",
        ORG_ID,
        _candidate(draft_item, 0.90),
    )

    assert result.answer_allowed is False
    assert result.reason == "sensitive_topic_unapproved_source"
    assert result.should_handoff is True
    assert result.should_log_unknown is False
    assert result.source_knowledge_item_id == ITEM_ID


def test_non_sensitive_unapproved_source_is_denied() -> None:
    """Even non-sensitive queries require an approved source (defense-in-depth)."""
    draft_item = _item(status="draft")
    result = evaluate_answer_policy(
        "where is the campus",
        "campus location address",
        ORG_ID,
        _candidate(draft_item, 0.90),
    )

    assert result.answer_allowed is False
    assert result.reason == "unapproved_source"


# ---------------------------------------------------------------------------
# Handoff response text
# ---------------------------------------------------------------------------


def test_denied_response_text_mentions_human_representative() -> None:
    """Every denied response must offer a human handoff."""
    for result in [
        evaluate_answer_policy("x", "x", ORG_ID, _candidate(None, 0.0)),
        evaluate_answer_policy("x", "x", ORG_ID, _candidate(_item(), 0.30)),
        evaluate_answer_policy("x", "fee cost", ORG_ID, _candidate(_item(), 0.72)),
    ]:
        assert "human representative" in result.response_text or "representative" in result.response_text
        assert result.answer_allowed is False


# ---------------------------------------------------------------------------
# Result fields completeness
# ---------------------------------------------------------------------------


def test_allowed_result_exposes_source_item_id() -> None:
    result = evaluate_answer_policy(
        "office hours",
        "office hours time",
        ORG_ID,
        _candidate(_item(item_id=ITEM_ID), 0.90),
    )
    assert result.source_knowledge_item_id == ITEM_ID
    assert result.confidence == 0.90
