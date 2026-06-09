from app.services.language.language_router import (
    choose_response_language,
    detect_language,
    normalize_text,
)

__all__ = [
    "choose_response_language",
    "detect_language",
    "detect_language_mode",
    "normalize_text",
]


def detect_language_mode(text: str) -> str:
    """Preserve the previous detector name while using the shared language router."""
    return detect_language(text)
