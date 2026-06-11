"""Unit tests for the deterministic call-summary outcome classification."""

import pytest

from app.services.analytics.call_summary import _determine_outcome


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeLead:
    def __init__(self, status: str) -> None:
        self.status = status


# ---------------------------------------------------------------------------
# Handoff always wins regardless of other signals
# ---------------------------------------------------------------------------


def test_handoff_outcome_when_handoff_reason_present() -> None:
    assert (
        _determine_outcome(
            answered_count=2,
            unanswered_count=0,
            lead=None,
            handoff_reason="policy_required",
        )
        == "handoff"
    )


def test_handoff_outcome_beats_lead_captured() -> None:
    assert (
        _determine_outcome(
            answered_count=1,
            unanswered_count=0,
            lead=_FakeLead("new"),
            handoff_reason="caller_requested",
        )
        == "handoff"
    )


# ---------------------------------------------------------------------------
# Lead captured (no handoff)
# ---------------------------------------------------------------------------


def test_lead_captured_outcome_when_lead_status_new() -> None:
    assert (
        _determine_outcome(
            answered_count=0,
            unanswered_count=1,
            lead=_FakeLead("new"),
            handoff_reason=None,
        )
        == "lead_captured"
    )


def test_lead_collecting_does_not_produce_lead_captured_outcome() -> None:
    """A partial lead (status=collecting) is not considered fully captured."""
    result = _determine_outcome(
        answered_count=1,
        unanswered_count=0,
        lead=_FakeLead("collecting"),
        handoff_reason=None,
    )
    assert result != "lead_captured"


# ---------------------------------------------------------------------------
# Answered / unknown / mixed
# ---------------------------------------------------------------------------


def test_answered_outcome_when_only_answered_turns() -> None:
    assert (
        _determine_outcome(
            answered_count=3,
            unanswered_count=0,
            lead=None,
            handoff_reason=None,
        )
        == "answered"
    )


def test_unknown_outcome_when_only_unanswered_turns() -> None:
    assert (
        _determine_outcome(
            answered_count=0,
            unanswered_count=2,
            lead=None,
            handoff_reason=None,
        )
        == "unknown"
    )


def test_mixed_outcome_when_both_answered_and_unknown() -> None:
    assert (
        _determine_outcome(
            answered_count=2,
            unanswered_count=1,
            lead=None,
            handoff_reason=None,
        )
        == "mixed"
    )


# ---------------------------------------------------------------------------
# No input
# ---------------------------------------------------------------------------


def test_no_input_outcome_when_zero_turns() -> None:
    assert (
        _determine_outcome(
            answered_count=0,
            unanswered_count=0,
            lead=None,
            handoff_reason=None,
        )
        == "no_input"
    )
