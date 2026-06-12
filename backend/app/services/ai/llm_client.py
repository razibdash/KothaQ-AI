"""Shared Groq LLM client factory.

Two tiers:
  get_llm()       → llama-3.3-70b-versatile   (quality, general use)
  get_fast_llm()  → llama-3.1-8b-instant       (speed-sensitive voice turns)

Both raise RuntimeError if GROQ_API_KEY is not configured.
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
    )


@lru_cache(maxsize=1)
def get_llm(temperature: float = 0.2) -> ChatGroq:
    """Quality LLM for response generation, intent analysis, and entity extraction."""
    return _build(get_settings().GROQ_MODEL, temperature)


@lru_cache(maxsize=1)
def get_fast_llm(temperature: float = 0.1) -> ChatGroq:
    """Fast LLM for latency-sensitive voice turns (< 500 ms target)."""
    return _build(get_settings().GROQ_FAST_MODEL, temperature)
