"""TwiML response builders for Twilio voice webhooks.

All public functions return a well-formed XML string that Twilio can execute.
Caller-supplied text is assigned to Element.text so ElementTree handles
XML-escaping automatically — no manual escaping is needed.
"""

import xml.etree.ElementTree as ET

_TWILIO_LANGUAGE_MAP: dict[str, str] = {
    "bn-BD": "bn-IN",
    "bn-Latn": "bn-IN",
    "syl-BD": "bn-IN",
    "en-US": "en-US",
    "en-GB": "en-GB",
}

_GATHER_TIMEOUT = "5"

# Single-word triggers for a human-handoff request.
_HANDOFF_KEYWORDS = frozenset(
    {
        "human",
        "agent",
        "operator",
        "transfer",
        "representative",
        "person",
        "মানুষ",
        "প্রতিনিধি",
        "manush",
        "porichalok",
    }
)

# Multi-word phrases that also trigger a handoff (checked as substrings).
_HANDOFF_PHRASES: tuple[str, ...] = (
    "admission officer",
    "admissions officer",
    "talk to someone",
    "speak to someone",
    "speak to a person",
    "অফিসে কথা বলবো",
    "অফিসে কথা বলব",
    "অফিসে কথা",
    "অফিসে বলবো",
    "office e kotha",
    "office kotha",
)

# Single-word exit signals.
_EXIT_KEYWORDS = frozenset(
    {
        "bye",
        "goodbye",
        "biday",   # Bengali transliteration
        "bidai",
    }
)

# Substring phrases that signal the caller wants to end the call.
_EXIT_PHRASES: tuple[str, ...] = (
    "thank you",
    "no thanks",
    "no thank you",
    "that's all",
    "thats all",
    "ar lagbe na",    # Banglish: আর লাগবে না
    "na lagbe na",    # Banglish variant
    "ar na",          # short Banglish variant
    "আর লাগবে না",
    "না লাগবে",
    "আর না",
    "ধন্যবাদ",        # Bengali: thank you
    "শেষ",            # Bengali: finished / done
)

# ---------------------------------------------------------------------------
# Localised phrase banks (keyed by language group)
# ---------------------------------------------------------------------------

_PROMPT: dict[str, str] = {
    "bn-BD": "আপনার প্রশ্নটি বলুন।",
    "bn-Latn": "Apnar proshno bolun.",
    "en": "Please say your question.",
}

_FOLLOW_UP: dict[str, str] = {
    "bn-BD": "আর কোনো প্রশ্ন আছে?",
    "bn-Latn": "Ar kono proshno ache?",
    "en": "Do you have another question?",
}

_GOODBYE: dict[str, str] = {
    "bn-BD": "ধন্যবাদ। বিদায়।",
    "bn-Latn": "Dhonnobad. Biday.",
    "en": "Thank you for calling. Goodbye.",
}

_NO_RESPONSE: dict[str, str] = {
    "bn-BD": "কিছু শুনতে পাইনি। বিদায়।",
    "bn-Latn": "Kichu shhunte paini. Biday.",
    "en": "I didn't hear anything. Goodbye.",
}

_RETRY: dict[str, str] = {
    "bn-BD": "বুঝতে পারিনি। আবার বলুন।",
    "bn-Latn": "Bujhte parini. Abar bolun.",
    "en": "I didn't catch that. Please try again.",
}

_HOLD: dict[str, str] = {
    "bn-BD": "অনুগ্রহ করে অপেক্ষা করুন।",
    "bn-Latn": "Anugroho kore opekkha korun.",
    "en": "Please hold while I connect you to a representative.",
}

_NO_HANDOFF: dict[str, str] = {
    "bn-BD": "দুঃখিত, এই মুহূর্তে সংযোগ দেওয়া সম্ভব হচ্ছে না। ধন্যবাদ।",
    "bn-Latn": "Dukkhito, ei muhurte connection dewa sambhob hosse na. Dhonnobad.",
    "en": "I'm sorry, I cannot connect you at this time. Please call again later. Goodbye.",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lang_group(language_code: str) -> str:
    if language_code == "bn-BD":
        return "bn-BD"
    if language_code in {"bn-Latn", "syl-BD"}:
        return "bn-Latn"
    return "en"


def _twilio_lang(language_code: str) -> str:
    return _TWILIO_LANGUAGE_MAP.get(language_code, "en-US")


def _to_twiml(root: ET.Element) -> str:
    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


def _say(parent: ET.Element, text: str, language_code: str) -> ET.Element:
    el = ET.SubElement(parent, "Say", language=_twilio_lang(language_code))
    el.text = text
    return el


def _gather(
    parent: ET.Element,
    *,
    action_url: str,
    language_code: str,
    prompt: str,
) -> ET.Element:
    gather = ET.SubElement(
        parent,
        "Gather",
        input="speech",
        action=action_url,
        method="POST",
        language=_twilio_lang(language_code),
        timeout=_GATHER_TIMEOUT,
        speechTimeout="auto",
    )
    _say(gather, prompt, language_code)
    return gather


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def caller_requests_handoff(speech_text: str) -> bool:
    """Return True when the caller's words explicitly ask for a human agent."""
    text = speech_text.casefold()
    if set(text.split()) & _HANDOFF_KEYWORDS:
        return True
    return any(phrase in text for phrase in _HANDOFF_PHRASES)


def caller_wants_to_exit(speech_text: str) -> bool:
    """Return True when the caller signals they want to end the call."""
    text = speech_text.casefold()
    if set(text.split()) & _EXIT_KEYWORDS:
        return True
    return any(phrase in text for phrase in _EXIT_PHRASES)


# ---------------------------------------------------------------------------
# TwiML builders
# ---------------------------------------------------------------------------


def greeting_twiml(
    org_name: str,
    org_slug: str,
    language_code: str,
    gather_action_url: str,
) -> str:
    """Incoming-call greeting followed by a Gather for the caller's question."""
    lg = _lang_group(language_code)
    root = ET.Element("Response")

    sep = "।" if lg != "en" else "."
    _say(root, f"{org_name}{sep} {_PROMPT[lg]}", language_code)
    _gather(root, action_url=gather_action_url, language_code=language_code, prompt=_PROMPT[lg])
    _say(root, _NO_RESPONSE[lg], language_code)

    return _to_twiml(root)


def answer_twiml(
    response_text: str,
    language_code: str,
    gather_action_url: str,
) -> str:
    """Speak the answer then offer to take another question."""
    lg = _lang_group(language_code)
    root = ET.Element("Response")

    _say(root, response_text, language_code)
    _gather(root, action_url=gather_action_url, language_code=language_code, prompt=_FOLLOW_UP[lg])
    _say(root, _GOODBYE[lg], language_code)

    return _to_twiml(root)


def retry_twiml(language_code: str, gather_action_url: str) -> str:
    """Ask the caller to repeat when no speech was captured."""
    lg = _lang_group(language_code)
    root = ET.Element("Response")

    _gather(root, action_url=gather_action_url, language_code=language_code, prompt=_RETRY[lg])
    _say(root, _NO_RESPONSE[lg], language_code)

    return _to_twiml(root)


def handoff_twiml(language_code: str, handoff_phone: str | None) -> str:
    """Transfer the caller to a human agent, or apologise if no number is configured."""
    lg = _lang_group(language_code)
    root = ET.Element("Response")

    if handoff_phone:
        _say(root, _HOLD[lg], language_code)
        dial = ET.SubElement(root, "Dial")
        dial.text = handoff_phone
    else:
        _say(root, _NO_HANDOFF[lg], language_code)

    return _to_twiml(root)


def goodbye_twiml(language_code: str) -> str:
    """Speak a polite farewell and hang up — no further input is expected."""
    lg = _lang_group(language_code)
    root = ET.Element("Response")
    _say(root, _GOODBYE[lg], language_code)
    ET.SubElement(root, "Hangup")
    return _to_twiml(root)


def build_say_response(message: str) -> str:
    """Minimal TwiML that speaks a single message (kept for backward compatibility)."""
    root = ET.Element("Response")
    say = ET.SubElement(root, "Say")
    say.text = message
    return _to_twiml(root)


# ---------------------------------------------------------------------------
# Adapter class — implements VoiceProvider protocol
# ---------------------------------------------------------------------------


class TwilioVoiceAdapter:
    """VoiceProvider implementation that produces Twilio-compatible TwiML XML."""

    content_type: str = "application/xml"

    def greeting(
        self,
        org_name: str,
        org_slug: str,
        language_code: str,
        gather_action_url: str,
    ) -> str:
        return greeting_twiml(org_name, org_slug, language_code, gather_action_url)

    def answer(
        self,
        response_text: str,
        language_code: str,
        gather_action_url: str,
    ) -> str:
        return answer_twiml(response_text, language_code, gather_action_url)

    def retry(
        self,
        language_code: str,
        gather_action_url: str,
    ) -> str:
        return retry_twiml(language_code, gather_action_url)

    def handoff(
        self,
        language_code: str,
        handoff_phone: str | None,
    ) -> str:
        return handoff_twiml(language_code, handoff_phone)

    def caller_requests_handoff(self, speech_text: str) -> bool:
        return caller_requests_handoff(speech_text)

    def goodbye(self, language_code: str) -> str:
        return goodbye_twiml(language_code)

    def caller_wants_to_exit(self, speech_text: str) -> bool:
        return caller_wants_to_exit(speech_text)
