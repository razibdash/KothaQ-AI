"""Unit tests for LLM-powered lead field extraction.

All tests run without a real Groq API call.  The LLM path is exercised by
monkeypatching ``_invoke_extraction_llm``.  The fallback path is exercised
by setting ``_LANGCHAIN_AVAILABLE = False`` or making the function raise.

Coverage targets:
  • is_extraction_llm_available() — all three gating conditions
  • extract_fields_llm() — LLM path, returns LLMLeadExtraction
  • extract_fields_llm() — returns None when LLM unavailable
  • extract_fields_llm() — returns None when LLM raises
  • apply_extraction() — uses LLM result when available
  • apply_extraction() — falls back to regex when LLM returns None
  • apply_extraction() — never overwrites existing fields
  • extract_callback_time() — uses LLM callback_time when available
  • extract_callback_time() — falls back to regex when LLM returns None
"""

from __future__ import annotations

import pytest

import app.services.leads.llm_extractor as extractor_mod
import app.services.leads.capture as capture_mod
from app.core.config import Settings
from app.services.leads.capture import (
    LeadFields,
    apply_extraction,
    extract_callback_time,
)
from app.services.leads.llm_extractor import (
    LLMLeadExtraction,
    extract_fields_llm,
    is_extraction_llm_available,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings_with_key(enabled: bool = True) -> Settings:
    return Settings(GROQ_API_KEY="gsk-test-key", LLM_RESPONSE_ENABLED=enabled)  # type: ignore[arg-type]


def _settings_no_key() -> Settings:
    return Settings(GROQ_API_KEY=None)


def _fake_extraction(
    name: str | None = None,
    interest: str | None = None,
    callback_time: str | None = None,
) -> LLMLeadExtraction:
    return LLMLeadExtraction(name=name, interest=interest, callback_time=callback_time)


# ---------------------------------------------------------------------------
# is_extraction_llm_available()
# ---------------------------------------------------------------------------


class TestIsExtractionLlmAvailable:
    def test_false_when_langchain_not_installed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(extractor_mod, "_LANGCHAIN_AVAILABLE", False)
        assert is_extraction_llm_available() is False

    def test_false_when_api_key_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(extractor_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(extractor_mod, "get_settings", _settings_no_key)
        assert is_extraction_llm_available() is False

    def test_false_when_llm_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(extractor_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(extractor_mod, "get_settings", lambda: _settings_with_key(enabled=False))
        assert is_extraction_llm_available() is False

    def test_true_when_all_conditions_met(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(extractor_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(extractor_mod, "get_settings", lambda: _settings_with_key())
        assert is_extraction_llm_available() is True


# ---------------------------------------------------------------------------
# extract_fields_llm() — LLM path
# ---------------------------------------------------------------------------


class TestExtractFieldsLlmPath:
    def _enable_llm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(extractor_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(extractor_mod, "get_settings", lambda: _settings_with_key())

    def test_returns_extraction_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        expected = _fake_extraction(name="Rahim", interest="MBA")
        self._enable_llm(monkeypatch)
        monkeypatch.setattr(extractor_mod, "_invoke_extraction_llm", lambda *_: expected)
        result = extract_fields_llm("my name is Rahim, I want MBA admission", "admission")
        assert result == expected

    def test_extracts_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._enable_llm(monkeypatch)
        monkeypatch.setattr(
            extractor_mod, "_invoke_extraction_llm",
            lambda *_: _fake_extraction(name="Sarah"),
        )
        result = extract_fields_llm("my name is Sarah", "admission")
        assert result is not None
        assert result.name == "Sarah"

    def test_extracts_interest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._enable_llm(monkeypatch)
        monkeypatch.setattr(
            extractor_mod, "_invoke_extraction_llm",
            lambda *_: _fake_extraction(interest="BSc Computer Science"),
        )
        result = extract_fields_llm("I want to apply for BSc Computer Science", "admission")
        assert result is not None
        assert result.interest == "BSc Computer Science"

    def test_extracts_callback_time(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._enable_llm(monkeypatch)
        monkeypatch.setattr(
            extractor_mod, "_invoke_extraction_llm",
            lambda *_: _fake_extraction(callback_time="tomorrow morning"),
        )
        result = extract_fields_llm("call me tomorrow morning", "callback")
        assert result is not None
        assert result.callback_time == "tomorrow morning"

    def test_extracts_all_fields_together(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._enable_llm(monkeypatch)
        all_fields = _fake_extraction(
            name="Karim",
            interest="MBA",
            callback_time="Friday afternoon",
        )
        monkeypatch.setattr(extractor_mod, "_invoke_extraction_llm", lambda *_: all_fields)
        result = extract_fields_llm("ami Karim, MBA niye Friday afternoon call korun", "admission")
        assert result is not None
        assert result.name == "Karim"
        assert result.interest == "MBA"
        assert result.callback_time == "Friday afternoon"

    def test_returns_none_fields_when_nothing_stated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._enable_llm(monkeypatch)
        monkeypatch.setattr(
            extractor_mod, "_invoke_extraction_llm",
            lambda *_: _fake_extraction(),
        )
        result = extract_fields_llm("okay sure", "admission")
        assert result is not None
        assert result.name is None
        assert result.interest is None
        assert result.callback_time is None

    def test_intent_is_passed_to_invoke(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[str] = []

        def capture_invoke(text: str, intent: str) -> LLMLeadExtraction:
            captured.append(intent)
            return _fake_extraction()

        self._enable_llm(monkeypatch)
        monkeypatch.setattr(extractor_mod, "_invoke_extraction_llm", capture_invoke)
        extract_fields_llm("some text", "pricing")
        assert captured == ["pricing"]


# ---------------------------------------------------------------------------
# extract_fields_llm() — fallback / error paths
# ---------------------------------------------------------------------------


class TestExtractFieldsLlmFallback:
    def test_returns_none_when_langchain_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(extractor_mod, "_LANGCHAIN_AVAILABLE", False)
        assert extract_fields_llm("my name is Sarah", "admission") is None

    def test_returns_none_when_key_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(extractor_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(extractor_mod, "get_settings", _settings_no_key)
        assert extract_fields_llm("my name is Sarah", "admission") is None

    def test_returns_none_when_llm_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def raise_quota(text: str, intent: str) -> LLMLeadExtraction:
            raise RuntimeError("quota exceeded")

        monkeypatch.setattr(extractor_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(extractor_mod, "get_settings", lambda: _settings_with_key())
        monkeypatch.setattr(extractor_mod, "_invoke_extraction_llm", raise_quota)
        assert extract_fields_llm("my name is Sarah", "admission") is None


# ---------------------------------------------------------------------------
# apply_extraction() — LLM integration
# ---------------------------------------------------------------------------


class TestApplyExtractionWithLlm:
    def _enable_llm_extractor(self, monkeypatch: pytest.MonkeyPatch, result: LLMLeadExtraction) -> None:
        monkeypatch.setattr(extractor_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(extractor_mod, "get_settings", lambda: _settings_with_key())
        monkeypatch.setattr(extractor_mod, "_invoke_extraction_llm", lambda *_: result)

    def test_uses_llm_name_when_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._enable_llm_extractor(monkeypatch, _fake_extraction(name="Salma"))
        fields = LeadFields(interest="CSE")
        result = apply_extraction(fields, "ami Salma bolchi CSE-te porte chai", "admission")
        assert result.name == "Salma"
        assert result.interest == "CSE"  # existing field not overwritten

    def test_uses_llm_interest_when_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._enable_llm_extractor(monkeypatch, _fake_extraction(interest="MBBS"))
        fields = LeadFields(name="Rahim")
        result = apply_extraction(fields, "MBBS-te bhorti hote chai", "admission")
        assert result.interest == "MBBS"
        assert result.name == "Rahim"  # existing field not overwritten

    def test_does_not_overwrite_existing_name_even_with_llm(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._enable_llm_extractor(monkeypatch, _fake_extraction(name="Ahmed"))
        fields = LeadFields(name="Rahim", interest="CSE")
        result = apply_extraction(fields, "my name is Ahmed", "admission")
        assert result.name == "Rahim"  # original preserved

    def test_does_not_overwrite_existing_interest_even_with_llm(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._enable_llm_extractor(monkeypatch, _fake_extraction(interest="MBA"))
        fields = LeadFields(interest="CSE", name="Rahim")
        result = apply_extraction(fields, "apply for MBA", "admission")
        assert result.interest == "CSE"  # original preserved

    def test_regex_fallback_when_llm_returns_none_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LLM returns empty extraction → regex extracts name from pattern."""
        self._enable_llm_extractor(monkeypatch, _fake_extraction())
        fields = LeadFields(interest="CSE")
        # "my name is Sarah" has no LLM name but the regex will find it
        result = apply_extraction(fields, "my name is Sarah", "admission")
        assert result.name == "Sarah"

    def test_regex_fallback_when_llm_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(extractor_mod, "_LANGCHAIN_AVAILABLE", False)
        fields = LeadFields(interest="CSE")
        result = apply_extraction(fields, "my name is John", "admission")
        assert result.name == "John"

    def test_no_change_when_nothing_extractable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(extractor_mod, "_LANGCHAIN_AVAILABLE", False)
        fields = LeadFields()
        result = apply_extraction(fields, "okay sure", "admission")
        assert result == fields


# ---------------------------------------------------------------------------
# extract_callback_time() — LLM integration
# ---------------------------------------------------------------------------


class TestExtractCallbackTimeWithLlm:
    def _enable_llm_extractor(
        self, monkeypatch: pytest.MonkeyPatch, callback_time: str | None
    ) -> None:
        monkeypatch.setattr(extractor_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(extractor_mod, "get_settings", lambda: _settings_with_key())
        monkeypatch.setattr(
            extractor_mod,
            "_invoke_extraction_llm",
            lambda *_: _fake_extraction(callback_time=callback_time),
        )

    def test_uses_llm_callback_time(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._enable_llm_extractor(monkeypatch, "shukrabar bikal")
        result = extract_callback_time("shukrabar bikal e call korun")
        assert result == "shukrabar bikal"

    def test_regex_fallback_when_llm_returns_no_callback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._enable_llm_extractor(monkeypatch, None)
        result = extract_callback_time("call me tomorrow morning")
        assert result is not None
        assert "tomorrow" in result.lower()

    def test_regex_fallback_when_llm_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(extractor_mod, "_LANGCHAIN_AVAILABLE", False)
        result = extract_callback_time("please reach me at 3pm")
        assert result is not None
        assert "3pm" in result.lower()

    def test_returns_none_when_nothing_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(extractor_mod, "_LANGCHAIN_AVAILABLE", False)
        assert extract_callback_time("I want to know the CSE admission fee") is None
