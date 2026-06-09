BANGLISH_TERMS = {
    "koto": "কত",
    "cost": "খরচ",
    "admission": "ভর্তি",
}


def normalize_banglish(text: str) -> str:
    words = text.lower().split()
    return " ".join(BANGLISH_TERMS.get(w, w) for w in words)
