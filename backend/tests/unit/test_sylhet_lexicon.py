import pytest

from app.services.language.language_router import detect_language, normalize_text
from app.services.language.sylhet_lexicon import (
    SYLHET_PHRASE_CONCEPTS,
    normalize_sylhet_friendly,
)


@pytest.mark.parametrize(
    ("phrase", "expected"),
    SYLHET_PHRASE_CONCEPTS.items(),
)
def test_every_sylhet_friendly_phrase_normalizes_to_search_concepts(
    phrase: str,
    expected: str,
) -> None:
    """Exercise every maintainable lexicon entry through the public normalizer."""
    assert normalize_text(phrase, detect_language(phrase)) == expected


def test_lexicon_covers_at_least_twenty_caller_phrases() -> None:
    """Keep broad practical coverage from shrinking accidentally."""
    assert len(SYLHET_PHRASE_CONCEPTS) >= 20


def test_lexicon_covers_each_required_search_topic() -> None:
    """Ensure the lexicon retains aliases for all required caller intents."""
    concepts = " ".join(SYLHET_PHRASE_CONCEPTS.values())

    for required_concept in (
        "fee",
        "office hours",
        "location",
        "admission",
        "documents",
        "scholarship",
        "human operator",
        "callback",
        "branch",
    ):
        assert required_concept in concepts


def test_longest_matching_phrase_wins() -> None:
    """Prefer a specific phrase when caller text contains a shorter alias too."""
    assert (
        normalize_sylhet_friendly("afne office koytay bondho koita")
        == "office hours closing time"
    )


def test_unknown_phrase_has_no_lexicon_match() -> None:
    """Allow the general language normalizer to handle unknown expressions."""
    assert normalize_sylhet_friendly("weather forecast tomorrow") is None
