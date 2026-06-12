"""LLM-powered lead field extraction with graceful fallback.

Extracts caller name, program/service interest, and callback time preference
from a single voice turn using Groq/LLaMA structured output (one LLM call for
all three fields).

When LangChain is unavailable the public functions return ``None`` so callers
fall back to their own regex/pattern logic without any code change.

Security: extracted values are length-bounded (max 80 / 120 chars) before
being returned so oversized LLM output cannot reach the database.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.logging import get_logger, log_event

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# LangChain availability guard
# ---------------------------------------------------------------------------

try:
    from langchain_core.messages import HumanMessage, SystemMessage  # noqa: F401
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LLMLeadExtraction:
    """Extracted lead fields returned from a single LLM call."""

    name: str | None = None
    interest: str | None = None
    callback_time: str | None = None


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def is_extraction_llm_available() -> bool:
    """True when the fast LLM can be used for field extraction."""
    if not _LANGCHAIN_AVAILABLE:
        return False
    settings = get_settings()
    return bool(settings.GROQ_API_KEY) and settings.LLM_RESPONSE_ENABLED


# ---------------------------------------------------------------------------
# Internal LLM call — monkeypatchable seam
# ---------------------------------------------------------------------------

_EXTRACTION_SYSTEM_PROMPT = (
    "Extract lead fields from an inbound voice caller message.\n"
    "Fields to extract:\n"
    "  name          — caller's name if they introduced themselves.\n"
    "                  Examples: 'my name is Rahim', 'ami Karim bolchi',\n"
    "                            'আমার নাম সালমা', 'আমি করিম বলছি'\n"
    "  interest      — specific program, course, or service the caller mentions.\n"
    "                  Examples: 'MBA', 'BSc Computer Science', 'nursing program',\n"
    "                            'CSE admission', 'MBBS'\n"
    "  callback_time — preferred callback time if stated.\n"
    "                  Examples: 'tomorrow morning', 'after 5pm', 'shukrabar bikal',\n"
    "                            'আগামীকাল সকাল', 'Monday afternoon'\n"
    "Return null for any field not mentioned. Keep values concise (max 80 characters).\n"
    "Respond ONLY with valid JSON. Do not add explanation."
)


def _invoke_extraction_llm(text: str, intent: str) -> LLMLeadExtraction:
    """Single LLM call that extracts all three fields at once.

    Separated for monkeypatching in tests.  The intent context is passed so
    the model focuses extraction on the right domain (e.g. for 'admission'
    intent, 'interest' means the program name).
    """
    from pydantic import BaseModel, Field  # noqa: PLC0415
    from langchain_core.messages import HumanMessage, SystemMessage  # noqa: PLC0415
    from app.services.ai.llm_client import get_fast_llm  # noqa: PLC0415

    class _ExtractionResult(BaseModel):
        name: str | None = Field(default=None, description="Caller's name if stated")
        interest: str | None = Field(
            default=None,
            description="Program or service the caller is interested in",
        )
        callback_time: str | None = Field(
            default=None,
            description="Preferred callback time if stated",
        )

    messages = [
        SystemMessage(
            content=_EXTRACTION_SYSTEM_PROMPT + f"\nCaller intent context: {intent}"
        ),
        HumanMessage(content=f"Caller said: {text}"),
    ]
    result = get_fast_llm().with_structured_output(_ExtractionResult).invoke(messages)

    # Bound field lengths before returning (safety: prevent oversized values in DB)
    name = (result.name or "").strip()[:80] or None
    interest = (result.interest or "").strip()[:80] or None
    callback_time = (result.callback_time or "").strip()[:120] or None

    return LLMLeadExtraction(name=name, interest=interest, callback_time=callback_time)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_fields_llm(text: str, intent: str) -> LLMLeadExtraction | None:
    """Extract name, interest, and callback time via LLM in one call.

    Returns ``None`` when LLM is unavailable or raises so callers can fall
    through to regex-based extraction without any special handling.
    """
    if not is_extraction_llm_available():
        return None
    try:
        result = _invoke_extraction_llm(text, intent)
        log_event(
            logger,
            logging.DEBUG,
            "extraction_llm_success",
            has_name=result.name is not None,
            has_interest=result.interest is not None,
            has_callback=result.callback_time is not None,
        )
        return result
    except Exception as exc:  # noqa: BLE001
        log_event(
            logger,
            logging.WARNING,
            "extraction_llm_fallback",
            reason=type(exc).__name__,
        )
        return None
