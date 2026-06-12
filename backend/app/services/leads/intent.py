"""Lead intent detection — LLM primary, keyword fallback.

When LangChain + Groq are available, intent is classified via structured output
(llama-3.1-8b-instant).  When unavailable (CI, Python 3.14, no API key) the
deterministic keyword token-match runs instead — all existing tests pass unchanged.

Security: LLM output is validated against ``_VALID_INTENTS`` before use so a
prompt-injection attempt in caller text cannot inject an arbitrary intent label.
"""

from __future__ import annotations

import logging

from app.core.config import get_settings
from app.core.logging import get_logger, log_event

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Keyword tables — deterministic fallback (also used in CI / Python 3.14)
# ---------------------------------------------------------------------------

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

# Allow-list for LLM output — prevents prompt injection from injecting arbitrary labels
_VALID_INTENTS: frozenset[str] = frozenset(_INTENT_PRIORITY)

# ---------------------------------------------------------------------------
# LangChain availability guard
# ---------------------------------------------------------------------------

try:
    from langchain_core.messages import HumanMessage, SystemMessage  # noqa: F401
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False

# ---------------------------------------------------------------------------
# LLM classification
# ---------------------------------------------------------------------------

_INTENT_SYSTEM_PROMPT = (
    "You classify the intent of inbound voice caller messages for a school or organisation.\n"
    "Valid intents:\n"
    "  admission   — wants to apply, enrol, or asks about the admission/enrolment process\n"
    "  appointment — wants to book a meeting or appointment\n"
    "  demo        — wants a demonstration, trial, or sample\n"
    "  visit       — wants to visit the campus or facility\n"
    "  callback    — wants to be called back or contacted\n"
    "  pricing     — asks about fees, costs, tuition, or pricing\n"
    "Return the intent as a JSON object with field 'intent' (string or null).\n"
    "If the message is a general FAQ question with no lead intent, return null.\n"
    "Respond ONLY with valid JSON. Do not add any explanation."
)


def is_intent_llm_available() -> bool:
    """True when the fast LLM can be used for intent classification."""
    if not _LANGCHAIN_AVAILABLE:
        return False
    settings = get_settings()
    return bool(settings.GROQ_API_KEY) and settings.LLM_RESPONSE_ENABLED


def _classify_with_llm(text: str) -> str | None:
    """Call the fast LLM with structured output and return a validated intent or None.

    Separated so tests can monkeypatch this function without touching LangChain.
    The output is validated against ``_VALID_INTENTS`` before returning so no
    caller-injected label can leak into business logic.
    """
    from pydantic import BaseModel, Field  # noqa: PLC0415
    from langchain_core.messages import HumanMessage, SystemMessage  # noqa: PLC0415
    from app.services.ai.llm_client import get_fast_llm  # noqa: PLC0415

    class _IntentResult(BaseModel):
        intent: str | None = Field(
            default=None,
            description=(
                "Caller's lead intent. One of: admission, appointment, demo, "
                "visit, callback, pricing. Null for general FAQ questions."
            ),
        )

    messages = [
        SystemMessage(content=_INTENT_SYSTEM_PROMPT),
        HumanMessage(content=f"Caller said: {text}"),
    ]
    result = get_fast_llm().with_structured_output(_IntentResult).invoke(messages)
    # Validate: reject any label outside the allowed set (prompt injection guard)
    if result.intent and result.intent in _VALID_INTENTS:
        return result.intent
    return None


# ---------------------------------------------------------------------------
# Keyword fallback
# ---------------------------------------------------------------------------

def _keyword_detect(text: str) -> str | None:
    """Token-level keyword match — deterministic, no network required."""
    tokens = frozenset(text.casefold().split())
    for intent in _INTENT_PRIORITY:
        if tokens & _INTENT_KEYWORDS[intent]:
            return intent
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_lead_intent(text: str) -> str | None:
    """Return the highest-priority lead intent found in caller text, or None.

    Uses LLM structured output when available (better Bangla/Banglish support);
    falls back to keyword matching when LLM is unavailable or raises.
    When the LLM is available and returns null the result is trusted — no keyword
    second-pass — since the LLM handles nuance keywords cannot.
    """
    if is_intent_llm_available():
        try:
            result = _classify_with_llm(text)
            log_event(
                logger,
                logging.DEBUG,
                "intent_classified_llm",
                intent=result,
            )
            return result
        except Exception as exc:  # noqa: BLE001
            log_event(
                logger,
                logging.WARNING,
                "intent_llm_fallback",
                reason=type(exc).__name__,
            )
    return _keyword_detect(text)
