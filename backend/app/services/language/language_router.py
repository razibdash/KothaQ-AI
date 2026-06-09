import unicodedata
from collections.abc import Sequence

from app.services.language.sylhet_lexicon import (
    SYLHET_MARKERS,
    normalize_sylhet_friendly,
)

SUPPORTED_LANGUAGE_CODES = frozenset(
    {
        "bn-BD",
        "bn-Latn",
        "syl-BD",
        "en-US",
        "en-GB",
    }
)

BANGLISH_MARKERS = frozenset(
    {
        "amar",
        "apnar",
        "bhorti",
        "bondho",
        "chai",
        "er",
        "hobe",
        "jonno",
        "ki",
        "kobe",
        "kokhon",
        "koto",
        "koyta",
        "koytay",
        "kothay",
        "lagbe",
        "vorti",
    }
)
TOKEN_ALIASES = {
    "admissions": "admission",
    "admissionor": "admission",
    "bhorti": "admission",
    "vorti": "admission",
    "ভর্তি": "admission",
    "কাগজ": "documents",
    "document": "documents",
    "papers": "documents",
    "needed": "requirements",
    "required": "requirements",
    "requirement": "requirements",
    "lagbe": "requirements",
    "lagbo": "requirements",
    "lagi": "requirements",
    "fee": "fee",
    "fees": "fee",
    "ফি": "fee",
    "খরচ": "cost",
    "kokhon": "time",
    "কখন": "time",
    "সময়": "time",
    "সময়": "time",
    "hour": "hours",
    "koyta": "hours",
    "koytay": "hours",
    "close": "closing",
    "closed": "closing",
    "closes": "closing",
    "bondho": "closing",
    "bondo": "closing",
    "অফিস": "office",
    "ঠিকানা": "location",
    "kothay": "location",
    "কোথায়": "location",
}
STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "amar",
        "apnar",
        "are",
        "can",
        "chai",
        "do",
        "does",
        "er",
        "for",
        "how",
        "hobe",
        "i",
        "is",
        "jonno",
        "me",
        "of",
        "please",
        "the",
        "to",
        "what",
        "which",
        "with",
        "koto",
        "কত",
        "কি",
        "কী",
    }
)


def _tokens(text: str) -> list[str]:
    """Split text into Unicode-aware lowercase search tokens."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    searchable = "".join(
        character
        if unicodedata.category(character)[0] in {"L", "M", "N"}
        else " "
        for character in normalized
    )
    return searchable.split()


def _has_bangla_script(text: str) -> bool:
    """Return whether text contains a character from the Bangla Unicode block."""
    return any("\u0980" <= character <= "\u09ff" for character in text)


def detect_language(text: str) -> str:
    """Detect a supported language mode using deterministic script and term rules."""
    tokens = set(_tokens(text))
    if _has_bangla_script(text):
        return "bn-BD"
    if tokens & SYLHET_MARKERS:
        return "syl-BD"
    if tokens & BANGLISH_MARKERS:
        return "bn-Latn"
    return "en-US"


def normalize_text(text: str, language_code: str) -> str:
    """Normalize caller text into stable concepts suitable for knowledge search."""
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        raise ValueError(f"unsupported language code: {language_code}")

    tokens = _tokens(text)
    token_set = set(tokens)

    if {"cse", "cost"} <= token_set and ({"koto", "কত"} & token_set):
        return "cse cost কত cse tuition fee"

    sylhet_concepts = normalize_sylhet_friendly(" ".join(tokens))
    if sylhet_concepts is not None:
        return sylhet_concepts

    admission_terms = {"admission", "admissionor", "bhorti", "vorti", "ভর্তি"}
    requirement_terms = {
        "documents",
        "document",
        "papers",
        "কাগজ",
        "lagbe",
        "lagbo",
        "lagi",
        "requirements",
    }
    if token_set & admission_terms and token_set & requirement_terms:
        return "admission documents requirements"

    closing_terms = {"bondho", "bondo", "close", "closed", "closes", "closing"}
    office_time_terms = {"kokhon", "koyta", "koytay", "time", "কখন", "সময়", "সময়"}
    if "office" in token_set and token_set & closing_terms and token_set & office_time_terms:
        return "office hours closing time"

    normalized_tokens = [
        TOKEN_ALIASES.get(token, token)
        for token in tokens
        if token not in STOP_WORDS
        and token not in SYLHET_MARKERS
    ]
    return " ".join(normalized_tokens)


def choose_response_language(
    caller_text: str,
    org_default: str,
    supported_languages: Sequence[str],
) -> str:
    """Choose the closest caller language enabled by the organization."""
    supported = tuple(dict.fromkeys(supported_languages))
    if not supported:
        return org_default
    if not caller_text.strip():
        return org_default if org_default in supported else supported[0]

    detected = detect_language(caller_text)
    if detected in supported:
        return detected

    fallbacks = {
        "bn-BD": ("bn-Latn",),
        "bn-Latn": ("bn-BD",),
        "syl-BD": ("bn-Latn", "bn-BD"),
        "en-US": ("en-GB",),
        "en-GB": ("en-US",),
    }
    for fallback in fallbacks[detected]:
        if fallback in supported:
            return fallback
    if org_default in supported:
        return org_default
    return supported[0]
