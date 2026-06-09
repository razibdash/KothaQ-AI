def detect_language_mode(text: str) -> str:
    ascii_ratio = sum(1 for c in text if ord(c) < 128) / max(len(text), 1)
    if ascii_ratio > 0.8:
        return "bn-Latn"
    return "bn-BD"
