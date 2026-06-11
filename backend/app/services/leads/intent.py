"""Deterministic lead-intent detection from inbound voice caller text."""

_INTENT_KEYWORDS: dict[str, frozenset[str]] = {
    "admission": frozenset({
        "admission", "admit", "apply", "application", "enroll",
        "bhorti", "vorti", "ভর্তি", "আবেদন",
    }),
    "appointment": frozenset({
        "appointment", "meeting", "schedule", "book", "slot",
        "অ্যাপয়েন্টমেন্ট", "মিটিং", "বুক",
    }),
    "demo": frozenset({
        "demo", "demonstration", "trial", "sample",
        "ডেমো", "দেখান",
    }),
    "visit": frozenset({
        "visit", "campus", "tour",
        "ক্যাম্পাস", "দেখতে",
    }),
    "callback": frozenset({
        "callback", "contact", "reach",
        "ফোন", "যোগাযোগ",
    }),
    "pricing": frozenset({
        "price", "pricing", "fee", "fees", "cost", "tuition", "charge",
        "খরচ", "ফি", "মূল্য",
    }),
}

# Priority order; first match wins when multiple intents are present
_INTENT_PRIORITY = ("admission", "appointment", "demo", "visit", "callback", "pricing")


def detect_lead_intent(text: str) -> str | None:
    """Return the highest-priority lead intent found in caller text, or None."""
    tokens = frozenset(text.casefold().split())
    for intent in _INTENT_PRIORITY:
        if tokens & _INTENT_KEYWORDS[intent]:
            return intent
    return None
