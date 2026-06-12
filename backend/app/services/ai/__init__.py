from __future__ import annotations


def get_llm():  # type: ignore[return]
    from app.services.ai.llm_client import get_llm as _get_llm

    return _get_llm()


def get_fast_llm():  # type: ignore[return]
    from app.services.ai.llm_client import get_fast_llm as _get_fast_llm

    return _get_fast_llm()


__all__ = ["get_llm", "get_fast_llm"]
