"""Shared Groq LLM client factory.

Two tiers:
  get_llm()       → llama-3.3-70b-versatile   (quality, general use)
  get_fast_llm()  → llama-3.1-8b-instant       (speed-sensitive voice turns, < 8 s budget)

Both raise RuntimeError if GROQ_API_KEY is not configured.
request_timeout is read from LLM_RESPONSE_TIMEOUT in config so every caller
gets the same ceiling without passing it explicitly.
"""

from functools import lru_cache

from langchain_groq import ChatGroq

from app.core.config import get_settings


def _build(model: str, temperature: float) -> ChatGroq:
    settings = get_settings()
    if not settings.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to your .env file to enable LLM features."
        )
    return ChatGroq(
        model=model,
        api_key=settings.GROQ_API_KEY.get_secret_value(),
        temperature=temperature,
        request_timeout=settings.LLM_RESPONSE_TIMEOUT,
    )


@lru_cache(maxsize=1)
def get_llm(temperature: float = 0.2) -> ChatGroq:
    """Quality LLM for general-purpose tasks (intent analysis, summaries)."""
    return _build(get_settings().GROQ_MODEL, temperature)


@lru_cache(maxsize=1)
def get_fast_llm(temperature: float = 0.1) -> ChatGroq:
    """Fast LLM for latency-sensitive voice turns (target < 8 s round-trip)."""
    return _build(get_settings().GROQ_FAST_MODEL, temperature)
