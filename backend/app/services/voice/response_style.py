"""Deterministic, fact-preserving formatting for phone-friendly replies."""

import re
from typing import Literal, cast

ResponseStyle = Literal[
    "formal_parent",
    "student_friendly",
    "corporate_formal",
    "international_english",
]

SUPPORTED_RESPONSE_STYLES = frozenset(
    {
        "formal_parent",
        "student_friendly",
        "corporate_formal",
        "international_english",
    }
)
DETAIL_MARKERS = frozenset(
    {
        "বিস্তারিত",
        "details",
        "detail",
        "explain",
        "full",
        "বিস্তারিতভাবে",
        "bistarito",
    }
)
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?।])\s+")

STYLE_OPENERS = {
    "bn-BD": {
        "formal_parent": "জি।",
        "student_friendly": "ঠিক আছে।",
        "corporate_formal": "অবশ্যই।",
        "international_english": "নিশ্চয়ই।",
    },
    "bn-Latn": {
        "formal_parent": "Ji.",
        "student_friendly": "Thik ache.",
        "corporate_formal": "Obosshoi.",
        "international_english": "Certainly.",
    },
    "en": {
        "formal_parent": "Certainly.",
        "student_friendly": "Sure.",
        "corporate_formal": "Certainly.",
        "international_english": "Certainly.",
    },
}

UNKNOWN_FALLBACKS = {
    "bn-BD": {
        "formal_parent": (
            "দুঃখিত, তথ্যটি আমি নিশ্চিতভাবে যাচাই করতে পারছি না। "
            "চাইলে আপনাকে একজন প্রতিনিধির সঙ্গে যুক্ত করতে পারি।"
        ),
        "student_friendly": (
            "এই তথ্যটি এখন নিশ্চিতভাবে বলতে পারছি না। "
            "চাইলে একজন প্রতিনিধির সঙ্গে কথা বলিয়ে দিতে পারি।"
        ),
        "corporate_formal": (
            "তথ্যটি যাচাই করা যায়নি। "
            "প্রয়োজনে একজন প্রতিনিধির সঙ্গে সংযোগ করে দিতে পারি।"
        ),
        "international_english": (
            "তথ্যটি নিশ্চিতভাবে যাচাই করা যায়নি। "
            "চাইলে আপনাকে একজন প্রতিনিধির সঙ্গে যুক্ত করতে পারি।"
        ),
    },
    "bn-Latn": {
        "formal_parent": (
            "Dukkhito, totthota nishchit vabe verify korte parchi na. "
            "Chaile apnake ekjon representative-er sathe connect korte pari."
        ),
        "student_friendly": (
            "Ei totthota ekhon confirm korte parchi na. "
            "Chaile ekjon representative-er sathe kotha boliye dite pari."
        ),
        "corporate_formal": (
            "Totthota verify kora jayni. "
            "Proyojone representative-er sathe connect korte pari."
        ),
        "international_english": (
            "Totthota reliably verify korte parchi na. "
            "Chaile human representative-er sathe connect korte pari."
        ),
    },
    "en": {
        "formal_parent": (
            "I am sorry, but I cannot verify that information confidently. "
            "I can connect you with a representative."
        ),
        "student_friendly": (
            "I cannot confirm that yet. "
            "I can connect you with someone who can help."
        ),
        "corporate_formal": (
            "That information could not be verified. "
            "I can connect you with a representative."
        ),
        "international_english": (
            "I cannot verify that information confidently. "
            "I can connect you with a human representative."
        ),
    },
}


def _language_group(language_code: str) -> str:
    """Map supported response codes to a template language group."""
    if language_code == "bn-BD":
        return "bn-BD"
    if language_code in {"bn-Latn", "syl-BD"}:
        return "bn-Latn"
    if language_code in {"en-US", "en-GB"}:
        return "en"
    raise ValueError(f"unsupported response language: {language_code}")


def _validate_style(style: str) -> ResponseStyle:
    """Validate a style string and return its narrowed response-style type."""
    if style not in SUPPORTED_RESPONSE_STYLES:
        raise ValueError(f"unsupported response style: {style}")
    return cast(ResponseStyle, style)


def _sentences(text: str) -> list[str]:
    """Split source text into complete sentences without rewriting factual words."""
    normalized = " ".join(text.split())
    return [
        sentence.strip()
        for sentence in SENTENCE_BOUNDARY.split(normalized)
        if sentence.strip()
    ]


def caller_requests_details(caller_text: str) -> bool:
    """Detect an explicit request for a fuller answer using deterministic markers."""
    normalized = caller_text.casefold()
    return any(marker.strip() in normalized for marker in DETAIL_MARKERS)


def unknown_answer_fallback(
    language_code: str,
    style: ResponseStyle,
) -> str:
    """Return a short localized uncertainty and human-handoff reply."""
    language_group = _language_group(language_code)
    validated_style = _validate_style(style)
    return UNKNOWN_FALLBACKS[language_group][validated_style]


def style_verified_answer(
    verified_answer: str,
    language_code: str,
    style: ResponseStyle,
    *,
    include_details: bool = False,
) -> str:
    """Create a short reply while retaining selected source sentences verbatim."""
    if not verified_answer.strip():
        raise ValueError("verified_answer is required")

    language_group = _language_group(language_code)
    validated_style = _validate_style(style)
    source_sentences = _sentences(verified_answer)
    factual_limit = 3 if include_details else 2
    factual_reply = " ".join(source_sentences[:factual_limit])

    if include_details and len(source_sentences) >= 3:
        return factual_reply

    opener = STYLE_OPENERS[language_group][validated_style]
    return f"{opener} {factual_reply}"
