"""LLM-powered voice response generator.

Responsibility
--------------
Take a *verified* answer (already fact-checked and tenant-scoped by the answer
policy) and rephrase it into short, natural, phone-friendly speech using the
Groq fast-LLM.  For denied / handoff turns it generates a polite "cannot help
right now" message.

The LLM is **only a formatter**.  It receives the already-approved text and
must not add, remove, or contradict any fact.  This guarantee is enforced by:
  1. The system prompt explicitly prohibiting new facts.
  2. The deterministic fallback path — if the LLM is unavailable or returns an
     empty/error response, ``response_style.py`` templates are used instead.

When to use deterministic fallback
------------------------------------
  • ``langchain_core`` or ``langchain_groq`` not installed (Python 3.14 / CI).
  • ``GROQ_API_KEY`` absent in environment.
  • ``LLM_RESPONSE_ENABLED=false`` in config (cost control / A/B testing).
  • LLM call raises any exception (network, quota, timeout).
  • LLM returns empty content.

Language support
----------------
  bn-BD      → Bangla script response
  bn-Latn    → Banglish (Latin-script Bangla)
  syl-BD     → treated as bn-Latn (Sylhet-friendly Banglish)
  en-US / en-GB → English
"""

from __future__ import annotations

import logging

from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.services.voice.response_style import (
    ResponseStyle,
    style_verified_answer,
    unknown_answer_fallback,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# LangChain availability check
# ---------------------------------------------------------------------------

try:
    from langchain_core.messages import HumanMessage, SystemMessage  # noqa: F401
    from langchain_groq import ChatGroq as _ChatGroq  # noqa: F401

    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False


# ---------------------------------------------------------------------------
# Language grouping
# ---------------------------------------------------------------------------

def _lang_group(language_code: str) -> str:
    """Map a response language code to the template language group."""
    if language_code == "bn-BD":
        return "bn"
    if language_code in {"bn-Latn", "syl-BD"}:
        return "bn-Latn"
    return "en"


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

# Per-style tone instruction injected into the system prompt.
_TONE: dict[str, dict[str, str]] = {
    "en": {
        "student_friendly": "Use a friendly, casual tone — like talking to a student.",
        "formal_parent": "Use a respectful, formal tone — suitable for parents and senior callers.",
        "corporate_formal": "Use a concise, professional tone — standard business English.",
        "international_english": "Use clear, neutral English — suitable for international callers.",
    },
    "bn": {
        "student_friendly": "বন্ধুত্বপূর্ণ ও সহজ ভাষায় কথা বলুন — ছাত্রদের উপযুক্ত।",
        "formal_parent": "ভদ্র ও আনুষ্ঠানিক ভাষায় কথা বলুন — অভিভাবকদের উপযুক্ত।",
        "corporate_formal": "পেশাদার ও সংক্ষিপ্ত ভাষায় কথা বলুন।",
        "international_english": "পরিষ্কার ও সরল ভাষায় কথা বলুন।",
    },
    "bn-Latn": {
        "student_friendly": "Bandhuttopurno ebong sohoj bhashay kotha bolun — chhatro der upojukto.",
        "formal_parent": "Bhadro ebong anushthanic bhashay kotha bolun — abhibhabokder upojukto.",
        "corporate_formal": "Professional ebong sankshipto bhashay kotha bolun.",
        "international_english": "Porishkar ebong shorol bhashay kotha bolun.",
    },
}

# System prompts — define role, output language, and hard constraints.
_SYSTEM_PROMPT_TEMPLATE: dict[str, str] = {
    "en": (
        "You are a voice assistant answering caller questions over the phone.\n"
        "Rephrase the provided answer into 1–2 short, natural sentences for speaking aloud.\n\n"
        "Rules — follow every one of them:\n"
        "• Maximum 2 sentences.\n"
        "• No bullet points, no lists, no markdown, no headers.\n"
        "• Do NOT add any fact that is not already in the provided answer.\n"
        "• Speak directly to the caller (use 'you' / 'your').\n"
        "• {tone}"
    ),
    "bn": (
        "আপনি একটি ভয়েস সহকারী যিনি ফোনে কলারের প্রশ্নের উত্তর দেন।\n"
        "প্রদত্ত উত্তরটি ফোনে বলার উপযুক্ত ১–২টি সংক্ষিপ্ত, স্বাভাবিক বাক্যে পুনরায় লিখুন।\n\n"
        "নিয়মাবলি — প্রতিটি মেনে চলুন:\n"
        "• সর্বোচ্চ ২টি বাক্য।\n"
        "• কোনো তালিকা, মার্কডাউন বা হেডার নয়।\n"
        "• প্রদত্ত উত্তরে নেই এমন কোনো তথ্য যোগ করবেন না।\n"
        "• কলারকে সরাসরি সম্বোধন করুন ('আপনি' ব্যবহার করুন)।\n"
        "• {tone}"
    ),
    "bn-Latn": (
        "Apni ekta voice assistant je phone-e callar er proshno-r uttor den.\n"
        "Dewa uttorta phone-e bolar upojukto 1–2 ti sংkshipto, swabhavic vakye likhun.\n\n"
        "Niyom — protitai manun:\n"
        "• Sorbochcho 2 ti bakyo.\n"
        "• Kono list, markdown ba header noy.\n"
        "• Dewa uttore nei emon kono tottho jog korben na.\n"
        "• Callarke shorashorivabe shombodhan korun ('apni' bybohar korun).\n"
        "• {tone}"
    ),
}

# Handoff user-turn prompts — instruct the LLM to generate a polite can't-help message.
_HANDOFF_USER_PROMPT: dict[str, str] = {
    "en": (
        "Generate a brief, polite message (1–2 sentences) saying you cannot provide "
        "the requested information right now and you will connect the caller to a human "
        "representative. Do not mention technical reasons."
    ),
    "bn": (
        "একটি সংক্ষিপ্ত, ভদ্র বার্তা (১–২টি বাক্য) তৈরি করুন যেখানে বলা হবে যে "
        "আপনি এই মুহূর্তে তথ্যটি দিতে পারছেন না এবং কলারকে একজন মানব প্রতিনিধির সাথে "
        "সংযুক্ত করবেন। প্রযুক্তিগত কারণ উল্লেখ করবেন না।"
    ),
    "bn-Latn": (
        "Ekta sংkshipto, bhadro message (1–2 bakyo) toiri korun jate bola hobe je "
        "apni ekhon ei tottho dite parchen na ebং callarke ekjon manob protinidhir "
        "shathe connect korben. Technical karon ullekh korben na."
    ),
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_system_prompt(language_code: str, style: str) -> str:
    """Construct the system prompt for a given language and response style."""
    group = _lang_group(language_code)
    tone = _TONE.get(group, _TONE["en"]).get(style, _TONE["en"]["student_friendly"])
    template = _SYSTEM_PROMPT_TEMPLATE.get(group, _SYSTEM_PROMPT_TEMPLATE["en"])
    return template.format(tone=tone)


def _invoke_llm(system_prompt: str, user_prompt: str) -> str:
    """Call the fast LLM and return stripped content.

    Separated into its own function so tests can monkeypatch it without
    touching LangChain internals.
    """
    from langchain_core.messages import HumanMessage, SystemMessage  # noqa: PLC0415

    from app.services.ai.llm_client import get_fast_llm  # noqa: PLC0415

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    response = get_fast_llm().invoke(messages)
    return (response.content or "").strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_llm_available() -> bool:
    """True when LLM response generation is fully operational.

    Requires all three:
      1. langchain_core + langchain_groq installed.
      2. GROQ_API_KEY set in environment.
      3. LLM_RESPONSE_ENABLED=true in config (allows opt-out for A/B testing).
    """
    if not _LANGCHAIN_AVAILABLE:
        return False
    settings = get_settings()
    return bool(settings.GROQ_API_KEY) and settings.LLM_RESPONSE_ENABLED


def generate_voice_response(
    verified_answer: str,
    language_code: str,
    style: str,
    *,
    include_details: bool = False,
) -> str:
    """Rephrase *verified_answer* into natural phone speech.

    The LLM receives only the already-approved answer text; it cannot invent
    new facts.  Falls back to ``style_verified_answer`` on any failure.

    Parameters
    ----------
    verified_answer:  Approved knowledge-base text from the answer policy.
    language_code:    Detected caller language (e.g. ``"en-US"``, ``"bn-BD"``).
    style:            Response style (e.g. ``"student_friendly"``).
    include_details:  When True ask the LLM to include up to 3 sentences.
    """
    if not is_llm_available():
        return style_verified_answer(
            verified_answer, language_code, style, include_details=include_details
        )

    group = _lang_group(language_code)
    sentence_limit = "3" if include_details else "2"
    user_prompt = (
        f"Answer to rephrase (max {sentence_limit} sentences):\n{verified_answer}"
    )
    if group != "en":
        user_prompt = (
            f"Rephrase this answer into {sentence_limit} sentences "
            f"in {'Bangla' if group == 'bn' else 'Banglish (Latin script)'}:\n"
            f"{verified_answer}"
        )

    try:
        system_prompt = _build_system_prompt(language_code, style)
        generated = _invoke_llm(system_prompt, user_prompt)
        if generated:
            log_event(
                logger,
                logging.DEBUG,
                "llm_response_generated",
                language=language_code,
                style=style,
            )
            return generated
    except Exception as exc:  # noqa: BLE001
        log_event(
            logger,
            logging.WARNING,
            "llm_response_fallback",
            reason=type(exc).__name__,
            language=language_code,
        )

    return style_verified_answer(
        verified_answer, language_code, style, include_details=include_details
    )


def generate_handoff_response(
    language_code: str,
    style: str,
    *,
    reason: str = "",
) -> str:
    """Generate a polite "cannot help, connecting to human" message.

    The *reason* parameter is for internal logging only — it is never passed
    to the LLM so callers never hear internal policy names like ``low_confidence``.
    Falls back to ``unknown_answer_fallback`` on any failure.
    """
    if not is_llm_available():
        return unknown_answer_fallback(language_code, style)

    group = _lang_group(language_code)
    user_prompt = _HANDOFF_USER_PROMPT.get(group, _HANDOFF_USER_PROMPT["en"])

    try:
        system_prompt = _build_system_prompt(language_code, style)
        generated = _invoke_llm(system_prompt, user_prompt)
        if generated:
            log_event(
                logger,
                logging.DEBUG,
                "llm_handoff_generated",
                language=language_code,
                style=style,
                policy_reason=reason,
            )
            return generated
    except Exception as exc:  # noqa: BLE001
        log_event(
            logger,
            logging.WARNING,
            "llm_handoff_fallback",
            reason=type(exc).__name__,
            language=language_code,
        )

    return unknown_answer_fallback(language_code, style)
