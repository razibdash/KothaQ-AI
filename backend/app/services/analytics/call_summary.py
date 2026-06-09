def summarize_call(turns: list[str]) -> str:
    return " \".join(turns)[:500]
