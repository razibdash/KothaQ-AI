import re
from typing import cast

import pytest

from app.services.voice.response_style import (
    ResponseStyle,
    SUPPORTED_RESPONSE_STYLES,
    caller_requests_details,
    style_verified_answer,
    unknown_answer_fallback,
)

LANGUAGE_CODES = ("bn-BD", "bn-Latn", "syl-BD", "en-US", "en-GB")
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?।])\s+")


def sentence_count(text: str) -> int:
    """Count phone-reply sentences using the production punctuation boundaries."""
    return len([part for part in SENTENCE_BOUNDARY.split(text) if part.strip()])


@pytest.mark.parametrize(
    ("language_code", "style"),
    [
        (language_code, style)
        for language_code in LANGUAGE_CODES
        for style in SUPPORTED_RESPONSE_STYLES
    ],
)
def test_unknown_fallback_exists_for_every_language_and_style(
    language_code: str,
    style: ResponseStyle,
) -> None:
    """Ensure every supported response combination has a short handoff reply."""
    response = unknown_answer_fallback(language_code, style)

    assert response
    assert sentence_count(response) <= 2


@pytest.mark.parametrize(
    ("language_code", "style"),
    [
        ("bn-BD", "formal_parent"),
        ("bn-Latn", "student_friendly"),
        ("en-US", "corporate_formal"),
        ("en-GB", "international_english"),
    ],
)
def test_verified_facts_are_preserved_verbatim(
    language_code: str,
    style: ResponseStyle,
) -> None:
    """Verify styling adds framing without rewriting source facts."""
    answer = "The admission fee is 5,000 BDT. Applications close on 30 June."

    response = style_verified_answer(answer, language_code, style)

    assert "The admission fee is 5,000 BDT." in response
    assert "Applications close on 30 June." in response


@pytest.mark.parametrize(
    ("answer", "language_code", "expected_opener"),
    [
        (
            "ভর্তি ফি ৫,০০০ টাকা। শেষ তারিখ ৩০ জুন।",
            "bn-BD",
            "ঠিক আছে।",
        ),
        (
            "Admission fee 5,000 taka. Last date 30 June.",
            "bn-Latn",
            "Thik ache.",
        ),
        (
            "The admission fee is 5,000 BDT. Applications close on 30 June.",
            "en-US",
            "Sure.",
        ),
    ],
)
def test_verified_reply_uses_selected_language_style(
    answer: str,
    language_code: str,
    expected_opener: str,
) -> None:
    """Use a localized opener while preserving the matching verified answer."""
    response = style_verified_answer(
        answer,
        language_code,
        "student_friendly",
    )

    assert response == f"{expected_opener} {answer}"


def test_long_faq_is_shortened_to_phone_friendly_sentences() -> None:
    """Shorten long FAQs by selecting complete source sentences."""
    answer = (
        "The admission fee is 5,000 BDT. "
        "Applications close on 30 June. "
        "Bring two photographs. "
        "The office is beside the main gate."
    )

    response = style_verified_answer(
        answer,
        "en-US",
        "student_friendly",
    )

    assert len(response) < len(answer)
    assert sentence_count(response) == 3
    assert "The admission fee is 5,000 BDT." in response
    assert "Applications close on 30 June." in response
    assert "Bring two photographs." not in response


def test_detail_request_allows_three_verified_sentences() -> None:
    """Return one extra factual sentence when the caller explicitly asks for details."""
    answer = (
        "The admission fee is 5,000 BDT. "
        "Applications close on 30 June. "
        "Bring two photographs. "
        "The office is beside the main gate."
    )

    response = style_verified_answer(
        answer,
        "en-US",
        "student_friendly",
        include_details=True,
    )

    assert response == (
        "The admission fee is 5,000 BDT. "
        "Applications close on 30 June. "
        "Bring two photographs."
    )


@pytest.mark.parametrize(
    "caller_text",
    [
        "Please give me full details",
        "bistarito bolen",
        "বিস্তারিত বলুন",
    ],
)
def test_detail_request_detection(caller_text: str) -> None:
    """Recognize deterministic detail-request markers in supported caller forms."""
    assert caller_requests_details(caller_text) is True


def test_response_style_validation() -> None:
    """Reject unsupported language and style values rather than silently guessing."""
    with pytest.raises(ValueError, match="unsupported response language"):
        unknown_answer_fallback("fr-FR", "student_friendly")

    with pytest.raises(ValueError, match="unsupported response style"):
        unknown_answer_fallback(
            "en-US",
            cast(ResponseStyle, "casual"),
        )
