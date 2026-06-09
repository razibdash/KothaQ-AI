import pytest

from app.services.language.language_router import (
    choose_response_language,
    detect_language,
    normalize_text,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ভর্তি ফি কত?", "bn-BD"),
        ("What documents are required?", "en-US"),
        ("admission er jonno ki ki lagbe", "bn-Latn"),
        ("CSE cost koto", "bn-Latn"),
        ("afne admissionor lagi kita lagbo", "syl-BD"),
    ],
)
def test_detect_language(text: str, expected: str) -> None:
    assert detect_language(text) == expected


@pytest.mark.parametrize(
    ("text", "language_code", "expected"),
    [
        ("cse cost koto", "bn-Latn", "cse cost কত cse tuition fee"),
        (
            "admission er jonno ki ki lagbe",
            "bn-Latn",
            "admission documents requirements",
        ),
        (
            "office koytay bondho",
            "bn-Latn",
            "office hours closing time",
        ),
        (
            "afne admissionor lagi kita lagbo",
            "syl-BD",
            "admission documents requirements",
        ),
        (
            "Which documents are required for admission?",
            "en-US",
            "admission documents requirements",
        ),
        ("ভর্তি ফি কত?", "bn-BD", "admission fee"),
    ],
)
def test_normalize_text(
    text: str,
    language_code: str,
    expected: str,
) -> None:
    assert normalize_text(text, language_code) == expected


def test_normalize_text_rejects_unknown_language_code() -> None:
    with pytest.raises(ValueError, match="unsupported language code"):
        normalize_text("hello", "fr-FR")


@pytest.mark.parametrize(
    ("text", "org_default", "supported", "expected"),
    [
        ("ভর্তি কবে?", "en-US", ("bn-BD", "en-US"), "bn-BD"),
        ("admission kobe", "en-US", ("bn-Latn", "en-US"), "bn-Latn"),
        ("afne kita chan", "bn-BD", ("syl-BD", "bn-BD"), "syl-BD"),
        ("Hello there", "bn-BD", ("bn-BD", "en-GB"), "en-GB"),
        ("afne kita chan", "en-US", ("bn-Latn", "en-US"), "bn-Latn"),
        ("", "bn-BD", ("bn-BD", "en-US"), "bn-BD"),
    ],
)
def test_choose_response_language(
    text: str,
    org_default: str,
    supported: tuple[str, ...],
    expected: str,
) -> None:
    assert choose_response_language(text, org_default, supported) == expected
