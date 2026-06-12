"""Unit tests for LLM-backed lead intent classification.

All tests run without a real Groq API call.  The LLM path is exercised by
monkeypatching ``_classify_with_llm`` (the single call-site).  The fallback
path is exercised by setting ``_LANGCHAIN_AVAILABLE = False``.

Coverage targets:
  • is_intent_llm_available() — all three gating conditions
  • detect_lead_intent() — LLM path returns result + None
  • detect_lead_intent() — keyword fallback on LLM exception
  • detect_lead_intent() — keyword fallback when LLM unavailable
  • _VALID_INTENTS guard — reject labels outside the allow-list
  • Existing keyword behaviour preserved via fallback path
"""

from __future__ import annotations

import pytest

import app.services.leads.intent as intent_mod
from app.core.config import Settings
from app.services.leads.intent import (
    _VALID_INTENTS,
    _classify_with_llm,
    detect_lead_intent,
    is_intent_llm_available,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings_with_key(enabled: bool = True) -> Settings:
    return Settings(GROQ_API_KEY="gsk-test-key", LLM_RESPONSE_ENABLED=enabled)  # type: ignore[arg-type]


def _settings_no_key() -> Settings:
    return Settings(GROQ_API_KEY=None)


# ---------------------------------------------------------------------------
# is_intent_llm_available()
# ---------------------------------------------------------------------------


class TestIsIntentLlmAvailable:
    def test_false_when_langchain_not_installed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(intent_mod, "_LANGCHAIN_AVAILABLE", False)
        assert is_intent_llm_available() is False

    def test_false_when_api_key_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(intent_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(intent_mod, "get_settings", _settings_no_key)
        assert is_intent_llm_available() is False

    def test_false_when_llm_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(intent_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(intent_mod, "get_settings", lambda: _settings_with_key(enabled=False))
        assert is_intent_llm_available() is False

    def test_true_when_all_conditions_met(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(intent_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(intent_mod, "get_settings", lambda: _settings_with_key())
        assert is_intent_llm_available() is True

    def test_returns_bool(self) -> None:
        assert isinstance(is_intent_llm_available(), bool)


# ---------------------------------------------------------------------------
# detect_lead_intent() — LLM path
# ---------------------------------------------------------------------------


class TestDetectLeadIntentLlmPath:
    def _enable_llm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(intent_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(intent_mod, "get_settings", lambda: _settings_with_key())

    @pytest.mark.parametrize(
        "label",
        ["admission", "appointment", "demo", "visit", "callback", "pricing"],
    )
    def test_returns_llm_label_for_all_valid_intents(
        self, monkeypatch: pytest.MonkeyPatch, label: str
    ) -> None:
        self._enable_llm(monkeypatch)
        monkeypatch.setattr(intent_mod, "_classify_with_llm", lambda _: label)
        assert detect_lead_intent("some caller text") == label

    def test_returns_none_when_llm_finds_no_intent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LLM null response is trusted — no second-pass with keywords."""
        self._enable_llm(monkeypatch)
        monkeypatch.setattr(intent_mod, "_classify_with_llm", lambda _: None)
        assert detect_lead_intent("what time does the office open") is None

    def test_llm_result_used_even_without_matching_keywords(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LLM can catch intent from phrasing that has no keyword match."""
        self._enable_llm(monkeypatch)
        # "আমাদের কলেজে পড়তে চাই" has no admission keyword but LLM understands it
        monkeypatch.setattr(intent_mod, "_classify_with_llm", lambda _: "admission")
        assert detect_lead_intent("আমাদের কলেজে পড়তে চাই") == "admission"

    def test_falls_back_to_keywords_on_llm_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def raise_timeout(_: str) -> str:
            raise RuntimeError("network timeout")

        self._enable_llm(monkeypatch)
        monkeypatch.setattr(intent_mod, "_classify_with_llm", raise_timeout)
        # "bhorti" is a keyword for admission
        assert detect_lead_intent("bhorti hote chai") == "admission"

    def test_falls_back_to_keywords_returns_none_when_no_keyword_match(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def raise_err(_: str) -> str:
            raise RuntimeError("quota")

        self._enable_llm(monkeypatch)
        monkeypatch.setattr(intent_mod, "_classify_with_llm", raise_err)
        assert detect_lead_intent("what time does the office open") is None


# ---------------------------------------------------------------------------
# detect_lead_intent() — keyword fallback (LLM unavailable)
# ---------------------------------------------------------------------------


class TestDetectLeadIntentKeywordFallback:
    """Verify that all pre-existing keyword behaviour is preserved when
    LLM is unavailable — these mirror test_lead_intent.py but via the
    fallback code path explicitly."""

    def _disable_llm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(intent_mod, "_LANGCHAIN_AVAILABLE", False)

    def test_detects_admission_english(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._disable_llm(monkeypatch)
        assert detect_lead_intent("I want to apply for admission") == "admission"

    def test_detects_admission_banglish(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._disable_llm(monkeypatch)
        assert detect_lead_intent("bhorti hote chai") == "admission"

    def test_detects_admission_bangla(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._disable_llm(monkeypatch)
        assert detect_lead_intent("ভর্তি হতে চাই") == "admission"

    def test_detects_pricing_bangla(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._disable_llm(monkeypatch)
        assert detect_lead_intent("খরচ কত") == "pricing"

    def test_returns_none_for_general_query(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._disable_llm(monkeypatch)
        assert detect_lead_intent("what time does the office open") is None

    def test_admission_beats_pricing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._disable_llm(monkeypatch)
        assert detect_lead_intent("admission fee koto") == "admission"


# ---------------------------------------------------------------------------
# _VALID_INTENTS guard
# ---------------------------------------------------------------------------


class TestValidIntentsGuard:
    def test_valid_intents_covers_all_expected_labels(self) -> None:
        expected = {"admission", "appointment", "demo", "visit", "callback", "pricing"}
        assert _VALID_INTENTS == expected

    def test_valid_intents_is_frozenset(self) -> None:
        assert isinstance(_VALID_INTENTS, frozenset)
