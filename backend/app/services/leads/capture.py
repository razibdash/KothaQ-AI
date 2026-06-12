"""Incremental lead-field extraction and next-question selection for voice calls.

Lifecycle of a lead across call turns:
  collecting  → mandatory fields (interest, name) still missing
  finalizing  → interest + name captured; asking for callback preference
  new         → all done; ready for human review
"""

import re
from dataclasses import dataclass, replace

# ---------------------------------------------------------------------------
# Lead field snapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LeadFields:
    """In-memory snapshot of captured lead fields.  None = not yet collected."""

    interest: str | None = None
    name: str | None = None
    phone_masked: str | None = None


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

_NAME_PATTERNS = [
    re.compile(r"\bmy name is\s+([\wঀ-৿]{2,40})", re.IGNORECASE),
    re.compile(r"\bami\s+([\wঀ-৿]{2,40})\s+bolchi", re.IGNORECASE),
    re.compile(r"আমার নাম\s+([\wঀ-৿]{2,40})"),
    re.compile(r"আমি\s+([\wঀ-৿]{2,40})\s+বলছি"),
]

_CALLBACK_PATTERNS = [
    re.compile(
        r"\b(tomorrow|today|tonight|morning|afternoon|evening|"
        r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b", re.IGNORECASE),
    re.compile(r"(আগামীকাল|আজ|সকাল|বিকেল|সন্ধ্যা|রাত)"),
]

_INTEREST_STOPWORDS = frozenset({
    "i", "want", "need", "like", "please", "am", "is", "are", "about",
    "the", "a", "an", "for", "in", "of", "to", "know", "can", "you",
    "information", "tell", "me", "we",
})

_INTENT_SYNONYMS: dict[str, frozenset[str]] = {
    "admission": frozenset({"admission", "admit", "apply", "bhorti", "vorti", "ভর্তি"}),
    "pricing": frozenset({"price", "fee", "fees", "cost", "tuition", "খরচ", "ফি"}),
    "demo": frozenset({"demo", "trial", "demonstration"}),
    "visit": frozenset({"visit", "tour", "campus"}),
    "callback": frozenset({"callback", "call", "contact"}),
    "appointment": frozenset({"appointment", "meeting", "schedule", "book"}),
}


def extract_name(text: str) -> str | None:
    """Extract caller's name from common self-introduction patterns."""
    for pattern in _NAME_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
    return None


def extract_callback_time(text: str) -> str | None:
    """Extract a free-text callback time preference from caller utterance.

    Tries LLM extraction first (better Bangla/Banglish coverage); falls back
    to regex patterns when LLM is unavailable.
    """
    from app.services.leads.llm_extractor import extract_fields_llm  # noqa: PLC0415

    llm_result = extract_fields_llm(text, "callback")
    if llm_result and llm_result.callback_time:
        return llm_result.callback_time

    found: list[str] = []
    seen_starts: set[int] = set()
    for pattern in _CALLBACK_PATTERNS:
        m = pattern.search(text)
        if m and m.start() not in seen_starts:
            found.append(m.group(0))
            seen_starts.add(m.start())
    return " ".join(found) if found else None


def extract_interest(text: str, intent: str) -> str | None:
    """Extract a program or service name from caller text near the intent keyword.

    Scans a 3-token window on both sides of the matched keyword, so that
    "MBA tuition fee" (program before keyword) works as well as
    "apply for CSE" (program after keyword).
    """
    tokens = text.split()
    synonyms = _INTENT_SYNONYMS.get(intent, frozenset())
    for i, token in enumerate(tokens):
        if token.casefold() in synonyms:
            window = tokens[max(0, i - 3) : i] + tokens[i + 1 : i + 4]
            filtered = [
                t for t in window
                if t.casefold() not in _INTEREST_STOPWORDS
                and t.casefold() not in synonyms
            ]
            if filtered:
                candidate = " ".join(filtered).strip(",.?!")
                if 2 <= len(candidate) <= 80:
                    return candidate
    return None


def apply_extraction(fields: LeadFields, text: str, intent: str) -> LeadFields:
    """Return updated LeadFields with any new values extractable from caller text.

    Tries LLM structured extraction first (one call for name + interest); falls
    back to regex/pattern helpers when LLM is unavailable.  Existing non-None
    fields are never overwritten.
    """
    from app.services.leads.llm_extractor import extract_fields_llm  # noqa: PLC0415

    llm_result = extract_fields_llm(text, intent)

    updates: dict = {}
    if fields.name is None:
        name = (llm_result.name if llm_result else None) or extract_name(text)
        if name:
            updates["name"] = name
    if fields.interest is None:
        interest = (llm_result.interest if llm_result else None) or extract_interest(text, intent)
        if interest:
            updates["interest"] = interest
    return replace(fields, **updates) if updates else fields


# ---------------------------------------------------------------------------
# Next-question selection
# ---------------------------------------------------------------------------

_LEAD_QUESTIONS: dict[str, dict[str, str]] = {
    "bn-BD": {
        "interest": "আপনি কোন প্রোগ্রাম বা সেবার বিষয়ে জানতে চান?",
        "name": "আপনার নামটি কী বলবেন?",
        "callback": "আপনাকে কখন ফোন করলে সুবিধা হবে?",
    },
    "bn-Latn": {
        "interest": "Apni kon program ba service niye jante chan?",
        "name": "Apnar naam ki bolben?",
        "callback": "Apnake kokhon phone korle shubidha hobe?",
    },
    "en": {
        "interest": "Which program or service are you interested in?",
        "name": "May I have your name please?",
        "callback": "When is a convenient time for us to call you back?",
    },
}

_MANDATORY_FIELDS = ("interest", "name")


def _lang_group(language_code: str) -> str:
    if language_code == "bn-BD":
        return "bn-BD"
    if language_code in {"bn-Latn", "syl-BD"}:
        return "bn-Latn"
    return "en"


def next_lead_question(fields: LeadFields, language_code: str) -> str | None:
    """Return the question for the next uncaptured mandatory field, or None if done."""
    lang = _lang_group(language_code)
    questions = _LEAD_QUESTIONS[lang]
    for field_name in _MANDATORY_FIELDS:
        if getattr(fields, field_name) is None:
            return questions[field_name]
    return None


def callback_question(language_code: str) -> str:
    """Return the callback-time question localised to the caller's language."""
    return _LEAD_QUESTIONS[_lang_group(language_code)]["callback"]


def is_lead_complete(fields: LeadFields) -> bool:
    """Return True when all mandatory fields (interest, name) have been captured."""
    return all(getattr(fields, f) is not None for f in _MANDATORY_FIELDS)
