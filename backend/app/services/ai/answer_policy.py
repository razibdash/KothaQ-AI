def enforce_verified_answer_policy(
    answer: str | None,
    confidence: float,
) -> tuple[str, bool]:
    """Allow verified answers and require handoff for missing or low-confidence facts."""
    if not answer or confidence < 0.65:
        return (
            "I am not fully sure about this information. "
            "I can connect you to a human representative.",
            True,
        )
    return answer, False
