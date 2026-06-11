"""Unit tests for incremental lead-field extraction and next-question selection."""

import pytest

from app.services.leads.capture import (
    LeadFields,
    apply_extraction,
    callback_question,
    extract_callback_time,
    extract_interest,
    extract_name,
    is_lead_complete,
    next_lead_question,
)


# ---------------------------------------------------------------------------
# extract_name
# ---------------------------------------------------------------------------


def test_extract_name_english_pattern() -> None:
    assert extract_name("my name is Sarah") == "Sarah"


def test_extract_name_banglish_pattern() -> None:
    assert extract_name("ami Rahim bolchi") == "Rahim"


def test_extract_name_bangla_pattern() -> None:
    assert extract_name("আমার নাম রাহিম") == "রাহিম"


def test_extract_name_bangla_speaking_pattern() -> None:
    assert extract_name("আমি করিম বলছি") == "করিম"


def test_extract_name_returns_none_when_no_pattern() -> None:
    assert extract_name("I am interested in CSE admission") is None


def test_extract_name_returns_none_for_very_short_match() -> None:
    # Single-character "names" should not be captured
    assert extract_name("my name is A") is None


# ---------------------------------------------------------------------------
# extract_callback_time
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected_fragment",
    [
        ("call me tomorrow morning", "tomorrow"),
        ("please reach me at 3pm", "3pm"),
        ("available on Friday afternoon", "Friday"),
        ("আগামীকাল ফোন করবেন", "আগামীকাল"),
    ],
)
def test_extract_callback_time_finds_fragments(text: str, expected_fragment: str) -> None:
    result = extract_callback_time(text)
    assert result is not None
    assert expected_fragment.casefold() in result.casefold()


def test_extract_callback_time_returns_none_for_unrelated_text() -> None:
    assert extract_callback_time("I want to know the CSE admission fee") is None


# ---------------------------------------------------------------------------
# extract_interest
# ---------------------------------------------------------------------------


def test_extract_interest_from_admission_phrase() -> None:
    result = extract_interest("I want to apply for CSE admission", "admission")
    assert result is not None
    assert "CSE" in result


def test_extract_interest_from_fee_phrase() -> None:
    result = extract_interest("what is the MBA tuition fee", "pricing")
    assert result is not None
    # "MBA" should appear in the extracted interest
    assert "MBA" in result


def test_extract_interest_returns_none_when_nothing_follows_keyword() -> None:
    assert extract_interest("I want to apply", "admission") is None


# ---------------------------------------------------------------------------
# apply_extraction — incremental, no overwrite
# ---------------------------------------------------------------------------


def test_apply_extraction_captures_name() -> None:
    fields = LeadFields(interest="CSE admission")
    result = apply_extraction(fields, "my name is John", "admission")
    assert result.name == "John"
    assert result.interest == "CSE admission"


def test_apply_extraction_captures_interest() -> None:
    fields = LeadFields(name="Rahim")
    result = apply_extraction(fields, "I want to apply for MBA admission", "admission")
    assert result.name == "Rahim"
    assert result.interest is not None


def test_apply_extraction_does_not_overwrite_existing_name() -> None:
    fields = LeadFields(name="Rahim", interest="CSE")
    result = apply_extraction(fields, "my name is Ahmed", "admission")
    assert result.name == "Rahim"


def test_apply_extraction_does_not_overwrite_existing_interest() -> None:
    fields = LeadFields(interest="BSc Computer Science")
    result = apply_extraction(fields, "I want to apply for MBA", "admission")
    assert result.interest == "BSc Computer Science"


def test_apply_extraction_no_change_when_nothing_extractable() -> None:
    fields = LeadFields()
    result = apply_extraction(fields, "okay sure", "admission")
    assert result == fields


# ---------------------------------------------------------------------------
# next_lead_question
# ---------------------------------------------------------------------------


def test_next_lead_question_asks_interest_first() -> None:
    fields = LeadFields()
    q = next_lead_question(fields, "en-US")
    assert q is not None
    assert "program" in q.lower() or "service" in q.lower()


def test_next_lead_question_asks_name_when_interest_known() -> None:
    fields = LeadFields(interest="CSE admission")
    q = next_lead_question(fields, "en-US")
    assert q is not None
    assert "name" in q.lower()


def test_next_lead_question_returns_none_when_complete() -> None:
    fields = LeadFields(interest="MBA", name="Rahim")
    assert next_lead_question(fields, "en-US") is None


def test_next_lead_question_bangla() -> None:
    fields = LeadFields()
    q = next_lead_question(fields, "bn-BD")
    assert q is not None
    # Should be in Bangla script
    assert any("ঀ" <= c <= "৿" for c in q)


def test_next_lead_question_banglish() -> None:
    fields = LeadFields(interest="CSE")
    q = next_lead_question(fields, "bn-Latn")
    assert q is not None
    assert "naam" in q.lower() or "name" in q.lower()


# ---------------------------------------------------------------------------
# callback_question
# ---------------------------------------------------------------------------


def test_callback_question_english() -> None:
    q = callback_question("en-US")
    assert "call" in q.lower() or "time" in q.lower()


def test_callback_question_bangla() -> None:
    q = callback_question("bn-BD")
    assert any("ঀ" <= c <= "৿" for c in q)


# ---------------------------------------------------------------------------
# is_lead_complete
# ---------------------------------------------------------------------------


def test_lead_complete_when_interest_and_name_set() -> None:
    assert is_lead_complete(LeadFields(interest="CSE", name="Rahim")) is True


def test_lead_incomplete_without_name() -> None:
    assert is_lead_complete(LeadFields(interest="CSE")) is False


def test_lead_incomplete_without_interest() -> None:
    assert is_lead_complete(LeadFields(name="Rahim")) is False


def test_lead_incomplete_when_empty() -> None:
    assert is_lead_complete(LeadFields()) is False
