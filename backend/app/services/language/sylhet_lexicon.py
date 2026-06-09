"""Practical Sylhet-friendly aliases for deterministic search normalization.

This module is not a full Sylheti language model, translator, or ASR system.
It captures common romanized caller expressions and maps them to stable search
concepts. Non-expert developers can extend a topic by adding another
``"caller phrase": "search concepts"`` entry below.
"""

SYLHET_PHRASE_CONCEPTS = {
    # Fees and costs
    "fee koto": "fee cost tuition",
    "fees koto": "fee cost tuition",
    "taka koto lagbo": "fee cost tuition",
    "khoros koto": "fee cost tuition",
    # Office opening and closing times
    "office kun shomoy": "office hours time",
    "office koytay khule": "office hours opening time",
    "office koytay bondho": "office hours closing time",
    "office kokhon bondho": "office hours closing time",
    # Location and address
    "office koi": "office location address",
    "campus koi": "campus location address",
    "kuno jaygay": "location address",
    "thikana kita": "location address",
    # Admission
    "bhorti loiba": "admission application",
    "admission kobe": "admission deadline",
    "admissionor khobor": "admission information",
    # Admission documents and requirements
    "kita kagoj lagbo": "admission documents requirements",
    "ki ki lagbo": "admission documents requirements",
    "admissionor lagi kita lagbo": "admission documents requirements",
    # Scholarship and waiver
    "scholarship ase ni": "scholarship waiver",
    "waiver ase ni": "scholarship waiver",
    "medha britti ase": "scholarship waiver",
    # Human operator and handoff
    "manushor loge kotha": "human operator handoff",
    "operator deo": "human operator handoff",
    "sir re deo": "human operator handoff",
    # Callback and contact
    "pore phone dio": "callback contact",
    "call back korba": "callback contact",
    "amar loge jogajog": "callback contact",
    # Branch selection and location
    "kun branch": "branch",
    "branch koi": "branch location",
    "sylhet branch": "sylhet branch location",
}

SYLHET_MARKERS = frozenset(
    {
        "afne",
        "ain",
        "ase",
        "deo",
        "dio",
        "gesoin",
        "kagoj",
        "khoros",
        "kita",
        "koi",
        "korba",
        "kun",
        "lagbo",
        "loge",
        "loiba",
        "oino",
        "shomoy",
        "zaitam",
    }
)


def normalize_sylhet_friendly(text: str) -> str | None:
    """Return concepts for the longest known phrase contained in caller text."""
    normalized = " ".join(text.casefold().split())
    padded_text = f" {normalized} "
    matches = [
        (phrase, concepts)
        for phrase, concepts in SYLHET_PHRASE_CONCEPTS.items()
        if f" {phrase} " in padded_text
    ]
    if not matches:
        return None
    _, concepts = max(matches, key=lambda match: len(match[0].split()))
    return concepts
