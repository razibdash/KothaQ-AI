"""Unit tests for the LLM response generator.

All tests run without a real Groq API call.  The LLM path is exercised by
monkeypatching ``_invoke_llm`` (the single call-site).  The fallback path is
exercised by setting ``_LANGCHAIN_AVAILABLE = False`` or by making
``_invoke_llm`` raise.

Coverage targets:
  • is_llm_available() — all three conditions (package, key, flag)
  • generate_voice_response() — LLM path, fallback path, error fallback
  • generate_handoff_response() — LLM path, fallback path, error fallback
  • _build_system_prompt() — every language × style combination is non-empty
  • policy reason is NOT leaked to the LLM user prompt
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

import app.services.ai.response_generator as gen_mod
from app.core.config import Settings
from app.services.ai.response_generator import (
    _build_system_prompt,
    generate_handoff_response,
    generate_voice_response,
    is_llm_available,
)
from app.services.voice.response_style import SUPPORTED_RESPONSE_STYLES

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VERIFIED_ANSWER = "The office is open Monday to Friday, 9 am to 5 pm."
_BANGLA_ANSWER = "অফিস সোমবার থেকে শুক্রবার সকাল ৯টা থেকে বিকেল ৫টা পর্যন্ত খোলা।"


def _settings_with_key(enabled: bool = True) -> Settings:
    return Settings(
        GROQ_API_KEY="gsk-test-key",  # type: ignore[arg-type]
        LLM_RESPONSE_ENABLED=enabled,
    )


def _settings_no_key() -> Settings:
    return Settings(GROQ_API_KEY=None)


# ---------------------------------------------------------------------------
# is_llm_available()
# ---------------------------------------------------------------------------


class TestIsLlmAvailable:
    def test_false_when_langchain_not_installed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gen_mod, "_LANGCHAIN_AVAILABLE", False)
        assert is_llm_available() is False

    def test_false_when_api_key_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gen_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(gen_mod, "get_settings", _settings_no_key)
        assert is_llm_available() is False

    def test_false_when_response_generation_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gen_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(gen_mod, "get_settings", lambda: _settings_with_key(enabled=False))
        assert is_llm_available() is False

    def test_true_when_all_conditions_met(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gen_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(gen_mod, "get_settings", lambda: _settings_with_key(enabled=True))
        assert is_llm_available() is True

    def test_returns_bool(self) -> None:
        assert isinstance(is_llm_available(), bool)


# ---------------------------------------------------------------------------
# _build_system_prompt()
# ---------------------------------------------------------------------------


class TestBuildSystemPrompt:
    @pytest.mark.parametrize("language", ["en-US", "en-GB", "bn-BD", "bn-Latn", "syl-BD"])
    @pytest.mark.parametrize("style", list(SUPPORTED_RESPONSE_STYLES))
    def test_non_empty_for_every_combination(self, language: str, style: str) -> None:
        prompt = _build_system_prompt(language, style)
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_bangla_prompt_is_in_bangla_script(self) -> None:
        prompt = _build_system_prompt("bn-BD", "student_friendly")
        assert any("ঀ" <= ch <= "৿" for ch in prompt)

    def test_english_prompt_contains_rules(self) -> None:
        prompt = _build_system_prompt("en-US", "student_friendly")
        assert "2 sentences" in prompt or "Maximum 2" in prompt

    def test_style_tone_is_injected(self) -> None:
        friendly = _build_system_prompt("en-US", "student_friendly")
        formal = _build_system_prompt("en-US", "formal_parent")
        assert friendly != formal


# ---------------------------------------------------------------------------
# generate_voice_response() — fallback path
# ---------------------------------------------------------------------------


class TestGenerateVoiceResponseFallback:
    def test_uses_template_when_llm_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gen_mod, "_LANGCHAIN_AVAILABLE", False)
        result = generate_voice_response(
            _VERIFIED_ANSWER, "en-US", "student_friendly"
        )
        # Deterministic template: opener + answer
        assert "Sure." in result
        assert "Monday to Friday" in result

    def test_uses_template_when_key_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gen_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(gen_mod, "get_settings", _settings_no_key)
        result = generate_voice_response(
            _VERIFIED_ANSWER, "en-US", "formal_parent"
        )
        assert "Monday to Friday" in result

    def test_uses_template_when_llm_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def raise_quota(*_: object) -> str:
            raise RuntimeError("quota")

        monkeypatch.setattr(gen_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(gen_mod, "get_settings", lambda: _settings_with_key())
        monkeypatch.setattr(gen_mod, "_invoke_llm", raise_quota)
        result = generate_voice_response(
            _VERIFIED_ANSWER, "en-US", "student_friendly"
        )
        assert "Monday to Friday" in result

    def test_uses_template_when_llm_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gen_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(gen_mod, "get_settings", lambda: _settings_with_key())
        monkeypatch.setattr(gen_mod, "_invoke_llm", lambda *_: "")
        result = generate_voice_response(
            _VERIFIED_ANSWER, "en-US", "student_friendly"
        )
        assert "Monday to Friday" in result

    def test_bangla_fallback_uses_bangla_template(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gen_mod, "_LANGCHAIN_AVAILABLE", False)
        result = generate_voice_response(
            _BANGLA_ANSWER, "bn-BD", "student_friendly"
        )
        assert any("ঀ" <= ch <= "৿" for ch in result)


# ---------------------------------------------------------------------------
# generate_voice_response() — LLM path
# ---------------------------------------------------------------------------


class TestGenerateVoiceResponseLlm:
    def test_returns_llm_output_when_available(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        llm_reply = "We're open Monday to Friday, 9 am to 5 pm — feel free to drop by!"
        monkeypatch.setattr(gen_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(gen_mod, "get_settings", lambda: _settings_with_key())
        monkeypatch.setattr(gen_mod, "_invoke_llm", lambda sys, usr: llm_reply)

        result = generate_voice_response(
            _VERIFIED_ANSWER, "en-US", "student_friendly"
        )
        assert result == llm_reply

    def test_system_prompt_sent_to_llm(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[str] = []

        def capture_invoke(sys_prompt: str, usr_prompt: str) -> str:
            captured.append(sys_prompt)
            return "Rephrased answer."

        monkeypatch.setattr(gen_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(gen_mod, "get_settings", lambda: _settings_with_key())
        monkeypatch.setattr(gen_mod, "_invoke_llm", capture_invoke)

        generate_voice_response(_VERIFIED_ANSWER, "en-US", "student_friendly")

        assert len(captured) == 1
        assert "2" in captured[0] or "sentences" in captured[0].lower()

    def test_user_prompt_contains_verified_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[str] = []

        def capture_invoke(sys_prompt: str, usr_prompt: str) -> str:
            captured.append(usr_prompt)
            return "Rephrased."

        monkeypatch.setattr(gen_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(gen_mod, "get_settings", lambda: _settings_with_key())
        monkeypatch.setattr(gen_mod, "_invoke_llm", capture_invoke)

        generate_voice_response(_VERIFIED_ANSWER, "en-US", "student_friendly")

        assert _VERIFIED_ANSWER in captured[0]

    def test_include_details_passes_3_sentence_limit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[str] = []

        def capture_invoke(sys_prompt: str, usr_prompt: str) -> str:
            captured.append(usr_prompt)
            return "Detailed rephrased."

        monkeypatch.setattr(gen_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(gen_mod, "get_settings", lambda: _settings_with_key())
        monkeypatch.setattr(gen_mod, "_invoke_llm", capture_invoke)

        generate_voice_response(
            _VERIFIED_ANSWER, "en-US", "student_friendly", include_details=True
        )
        assert "3" in captured[0]


# ---------------------------------------------------------------------------
# generate_handoff_response() — fallback path
# ---------------------------------------------------------------------------


class TestGenerateHandoffResponseFallback:
    def test_uses_template_when_llm_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gen_mod, "_LANGCHAIN_AVAILABLE", False)
        result = generate_handoff_response("en-US", "student_friendly")
        assert "connect you with someone" in result

    def test_uses_bangla_template_when_llm_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gen_mod, "_LANGCHAIN_AVAILABLE", False)
        result = generate_handoff_response("bn-BD", "student_friendly")
        assert any("ঀ" <= ch <= "৿" for ch in result)

    def test_uses_template_when_llm_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def raise_timeout(*_: object) -> str:
            raise RuntimeError("timeout")

        monkeypatch.setattr(gen_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(gen_mod, "get_settings", lambda: _settings_with_key())
        monkeypatch.setattr(gen_mod, "_invoke_llm", raise_timeout)
        result = generate_handoff_response("en-US", "student_friendly")
        assert isinstance(result, str)
        assert len(result) > 10


# ---------------------------------------------------------------------------
# generate_handoff_response() — LLM path
# ---------------------------------------------------------------------------


class TestGenerateHandoffResponseLlm:
    def test_returns_llm_output_when_available(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        llm_reply = "I'm sorry, I can't find that information right now. Let me connect you with our team."
        monkeypatch.setattr(gen_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(gen_mod, "get_settings", lambda: _settings_with_key())
        monkeypatch.setattr(gen_mod, "_invoke_llm", lambda sys, usr: llm_reply)

        result = generate_handoff_response("en-US", "student_friendly", reason="low_confidence")
        assert result == llm_reply

    def test_policy_reason_not_in_user_prompt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Internal policy names must never reach the LLM user prompt."""
        captured: list[str] = []

        def capture_invoke(sys_prompt: str, usr_prompt: str) -> str:
            captured.append(usr_prompt)
            return "Polite handoff."

        monkeypatch.setattr(gen_mod, "_LANGCHAIN_AVAILABLE", True)
        monkeypatch.setattr(gen_mod, "get_settings", lambda: _settings_with_key())
        monkeypatch.setattr(gen_mod, "_invoke_llm", capture_invoke)

        for internal_reason in ("low_confidence", "cross_tenant_source", "unapproved_source"):
            captured.clear()
            generate_handoff_response("en-US", "student_friendly", reason=internal_reason)
            assert internal_reason not in captured[0], (
                f"Internal policy reason '{internal_reason}' must not be sent to the LLM"
            )
