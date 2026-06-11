"""Unit tests for deterministic lead-intent detection."""

import pytest

from app.services.leads.intent import detect_lead_intent


# ---------------------------------------------------------------------------
# Positive detections
# ---------------------------------------------------------------------------


def test_detects_admission_english() -> None:
    assert detect_lead_intent("I want to apply for admission") == "admission"


def test_detects_admission_banglish() -> None:
    assert detect_lead_intent("bhorti hote chai") == "admission"


def test_detects_admission_bangla() -> None:
    assert detect_lead_intent("ভর্তি হতে চাই") == "admission"


def test_detects_pricing() -> None:
    assert detect_lead_intent("what is the tuition fee") == "pricing"


def test_detects_pricing_banglish() -> None:
    assert detect_lead_intent("fee koto") == "pricing"


def test_detects_pricing_bangla() -> None:
    assert detect_lead_intent("খরচ কত") == "pricing"


def test_detects_appointment() -> None:
    assert detect_lead_intent("I want to book an appointment") == "appointment"


def test_detects_demo() -> None:
    assert detect_lead_intent("can I get a demo") == "demo"


def test_detects_visit() -> None:
    assert detect_lead_intent("I would like to visit the campus") == "visit"


def test_detects_callback() -> None:
    assert detect_lead_intent("please contact me") == "callback"


# ---------------------------------------------------------------------------
# Priority: admission beats pricing when both keywords present
# ---------------------------------------------------------------------------


def test_admission_takes_priority_over_pricing() -> None:
    assert detect_lead_intent("admission fee koto") == "admission"


def test_appointment_takes_priority_over_pricing() -> None:
    assert detect_lead_intent("book an appointment, what is the cost?") == "appointment"


# ---------------------------------------------------------------------------
# No intent for general FAQ questions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "what time does the office open",
        "where is the library",
        "অফিস কখন খোলে",
        "office kokhon khule",
        "my name is Rahim",
    ],
)
def test_no_intent_for_general_queries(text: str) -> None:
    assert detect_lead_intent(text) is None


# ---------------------------------------------------------------------------
# Case insensitivity
# ---------------------------------------------------------------------------


def test_case_insensitive_detection() -> None:
    assert detect_lead_intent("APPLY FOR ADMISSION") == "admission"
    assert detect_lead_intent("Tuition FEE") == "pricing"
