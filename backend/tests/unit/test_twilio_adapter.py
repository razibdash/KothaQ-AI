"""Unit tests for TwilioVoiceAdapter.

Tests verify that each adapter method produces well-formed TwiML XML with the
expected elements and attributes for both English and Bengali language codes.
"""

import xml.etree.ElementTree as ET

import pytest

from app.services.telephony.twilio_adapter import TwilioVoiceAdapter

_GATHER_URL = "https://example.com/api/v1/voice/gather/test-org"

adapter = TwilioVoiceAdapter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(xml_string: str) -> ET.Element:
    return ET.fromstring(xml_string)


def _child_tags(root: ET.Element) -> list[str]:
    return [child.tag for child in root]


# ---------------------------------------------------------------------------
# content_type
# ---------------------------------------------------------------------------


def test_content_type_is_xml() -> None:
    assert adapter.content_type == "application/xml"


# ---------------------------------------------------------------------------
# greeting
# ---------------------------------------------------------------------------


def test_greeting_returns_xml_declaration() -> None:
    result = adapter.greeting("Acme", "acme", "en-US", _GATHER_URL)
    assert result.startswith("<?xml")


def test_greeting_has_say_and_gather_en() -> None:
    root = _parse(adapter.greeting("Acme School", "acme", "en-US", _GATHER_URL))
    tags = _child_tags(root)
    assert "Say" in tags
    assert "Gather" in tags


def test_greeting_gather_action_url() -> None:
    root = _parse(adapter.greeting("Acme", "acme", "en-US", _GATHER_URL))
    gather = root.find("Gather")
    assert gather is not None
    assert gather.attrib["action"] == _GATHER_URL
    assert gather.attrib["method"] == "POST"
    assert gather.attrib["input"] == "speech"


def test_greeting_org_name_in_say_text() -> None:
    root = _parse(adapter.greeting("Green Valley Clinic", "gvc", "en-US", _GATHER_URL))
    first_say = root.find("Say")
    assert first_say is not None
    assert "Green Valley Clinic" in (first_say.text or "")


def test_greeting_bengali_language() -> None:
    root = _parse(adapter.greeting("ঢাকা ক্লিনিক", "dhaka", "bn-BD", _GATHER_URL))
    gather = root.find("Gather")
    assert gather is not None
    assert gather.attrib["language"] == "bn-IN"


# ---------------------------------------------------------------------------
# answer
# ---------------------------------------------------------------------------


def test_answer_has_say_and_gather() -> None:
    root = _parse(adapter.answer("Admission opens in January.", "en-US", _GATHER_URL))
    tags = _child_tags(root)
    assert "Say" in tags
    assert "Gather" in tags


def test_answer_first_say_contains_response_text() -> None:
    root = _parse(adapter.answer("Office hours are 9-5.", "en-US", _GATHER_URL))
    first_say = root.find("Say")
    assert first_say is not None
    assert "Office hours are 9-5." in (first_say.text or "")


def test_answer_no_dial_element() -> None:
    root = _parse(adapter.answer("Some answer.", "en-US", _GATHER_URL))
    assert root.find("Dial") is None


def test_answer_gather_points_to_action_url() -> None:
    root = _parse(adapter.answer("Some answer.", "en-US", _GATHER_URL))
    gather = root.find("Gather")
    assert gather is not None
    assert gather.attrib["action"] == _GATHER_URL


# ---------------------------------------------------------------------------
# retry
# ---------------------------------------------------------------------------


def test_retry_has_gather_no_dial() -> None:
    root = _parse(adapter.retry("en-US", _GATHER_URL))
    assert root.find("Gather") is not None
    assert root.find("Dial") is None


def test_retry_gather_action_url() -> None:
    root = _parse(adapter.retry("en-US", _GATHER_URL))
    gather = root.find("Gather")
    assert gather is not None
    assert gather.attrib["action"] == _GATHER_URL


def test_retry_bengali() -> None:
    root = _parse(adapter.retry("bn-BD", _GATHER_URL))
    gather = root.find("Gather")
    assert gather is not None
    nested_say = gather.find("Say")
    assert nested_say is not None
    assert nested_say.text  # localised prompt present


# ---------------------------------------------------------------------------
# handoff
# ---------------------------------------------------------------------------


def test_handoff_with_phone_has_dial() -> None:
    root = _parse(adapter.handoff("en-US", "+15551234567"))
    dial = root.find("Dial")
    assert dial is not None
    assert dial.text == "+15551234567"


def test_handoff_with_phone_has_hold_say() -> None:
    root = _parse(adapter.handoff("en-US", "+15551234567"))
    assert root.find("Say") is not None


def test_handoff_without_phone_no_dial() -> None:
    root = _parse(adapter.handoff("en-US", None))
    assert root.find("Dial") is None


def test_handoff_without_phone_has_apology_say() -> None:
    root = _parse(adapter.handoff("en-US", None))
    say = root.find("Say")
    assert say is not None
    assert say.text  # apology message present


def test_handoff_bengali_with_phone() -> None:
    root = _parse(adapter.handoff("bn-BD", "+8801700000000"))
    dial = root.find("Dial")
    assert dial is not None and dial.text == "+8801700000000"
    say = root.find("Say")
    assert say is not None
    assert say.attrib.get("language") == "bn-IN"


# ---------------------------------------------------------------------------
# caller_requests_handoff
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "I want to talk to a human",
        "Can I speak to an agent please",
        "transfer me",
        "I need a representative",
        "মানুষ দরকার",
        "manush er sathe kotha bolte chai",
    ],
)
def test_caller_requests_handoff_true(text: str) -> None:
    assert adapter.caller_requests_handoff(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "When does admission open?",
        "What are your office hours?",
        "আমার ভর্তির তারিখ কী?",
    ],
)
def test_caller_requests_handoff_false(text: str) -> None:
    assert adapter.caller_requests_handoff(text) is False
