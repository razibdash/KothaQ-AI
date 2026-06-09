import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.knowledge_item import KnowledgeItem

VERIFIED_CONFIDENCE_THRESHOLD = 0.65
TERM_ALIASES = {
    "admission": "admission",
    "admissions": "admission",
    "bhorti": "admission",
    "vorti": "admission",
    "ভর্তি": "admission",
    "fee": "fee",
    "fees": "fee",
    "cost": "fee",
    "খরচ": "fee",
    "ফি": "fee",
    "document": "document",
    "documents": "document",
    "papers": "document",
    "কাগজ": "document",
    "scholarship": "scholarship",
    "বৃত্তি": "scholarship",
    "waiver": "waiver",
    "office": "office",
    "অফিস": "office",
    "hour": "hours",
    "hours": "hours",
    "time": "hours",
    "kokhon": "hours",
    "কখন": "hours",
    "সময়": "hours",
    "সময়": "hours",
    "location": "location",
    "address": "location",
    "where": "location",
    "kothay": "location",
    "কোথায়": "location",
    "ঠিকানা": "location",
    "program": "program",
    "programs": "program",
    "course": "program",
    "courses": "program",
    "বিষয়": "program",
    "deadline": "deadline",
    "শেষ": "deadline",
    "payment": "payment",
    "pay": "payment",
    "পেমেন্ট": "payment",
    "যোগাযোগ": "contact",
    "contact": "contact",
    "callback": "callback",
    "call": "callback",
}
STOP_WORDS = {
    "a",
    "an",
    "are",
    "can",
    "do",
    "does",
    "for",
    "how",
    "i",
    "is",
    "me",
    "of",
    "please",
    "the",
    "to",
    "what",
    "which",
    "with",
    "koto",
    "কত",
    "কি",
    "কী",
}


@dataclass(frozen=True)
class KnowledgeSearchResult:
    answer: str | None
    confidence: float
    source_id: UUID | None

    @classmethod
    def no_verified_answer(cls, confidence: float = 0.0) -> "KnowledgeSearchResult":
        return cls(answer=None, confidence=confidence, source_id=None)


def _tokenize_search_text(text: str) -> list[str]:
    searchable = "".join(
        character
        if unicodedata.category(character)[0] in {"L", "M", "N"}
        else " "
        for character in text
    )
    return searchable.split()


def normalize_search_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    tokens = [
        TERM_ALIASES.get(token, token)
        for token in _tokenize_search_text(normalized)
        if token not in STOP_WORDS
    ]
    return " ".join(tokens)


def _score_candidate(query: str, item: KnowledgeItem) -> float:
    normalized_question = normalize_search_text(item.question)
    normalized_tags = normalize_search_text(" ".join(item.tags))
    candidate = " ".join(part for part in (normalized_question, normalized_tags) if part)
    if not query or not candidate:
        return 0.0

    query_tokens = set(query.split())
    candidate_tokens = set(candidate.split())
    unmatched_candidates = set(candidate_tokens)
    overlap_count = 0
    for query_token in query_tokens:
        exact_match = query_token if query_token in unmatched_candidates else None
        fuzzy_match = exact_match or next(
            (
                candidate_token
                for candidate_token in unmatched_candidates
                if SequenceMatcher(None, query_token, candidate_token).ratio() >= 0.82
            ),
            None,
        )
        if fuzzy_match is not None:
            overlap_count += 1
            unmatched_candidates.remove(fuzzy_match)

    query_coverage = overlap_count / len(query_tokens)
    candidate_precision = overlap_count / len(candidate_tokens)
    fuzzy_ratio = SequenceMatcher(None, query, normalized_question).ratio()
    score = (0.65 * query_coverage) + (0.20 * candidate_precision) + (0.15 * fuzzy_ratio)
    if len(query_tokens) > 1 and query_coverage < 0.75:
        return min(score, VERIFIED_CONFIDENCE_THRESHOLD - 0.01)
    return min(score, 1.0)


def _branch_belongs_to_organization(
    session: Session,
    organization_id: UUID,
    branch_id: UUID,
) -> bool:
    statement = select(Branch.id).where(
        Branch.id == branch_id,
        Branch.organization_id == organization_id,
    )
    return session.scalar(statement) is not None


def search_knowledge(
    session: Session,
    organization_id: UUID,
    query: str,
    *,
    branch_id: UUID | None = None,
    confidence_threshold: float = VERIFIED_CONFIDENCE_THRESHOLD,
) -> KnowledgeSearchResult:
    if branch_id is not None and not _branch_belongs_to_organization(
        session,
        organization_id,
        branch_id,
    ):
        return KnowledgeSearchResult.no_verified_answer()

    filters = [
        KnowledgeItem.organization_id == organization_id,
        KnowledgeItem.status == "approved",
    ]
    if branch_id is not None:
        filters.append(
            or_(
                KnowledgeItem.branch_id.is_(None),
                KnowledgeItem.branch_id == branch_id,
            )
        )

    items = list(session.scalars(select(KnowledgeItem).where(*filters)))
    normalized_query = normalize_search_text(query)
    if not normalized_query or not items:
        return KnowledgeSearchResult.no_verified_answer()

    best_item: KnowledgeItem | None = None
    best_score = 0.0
    for item in items:
        score = _score_candidate(normalized_query, item)
        if score > best_score:
            best_item = item
            best_score = score

    rounded_score = round(best_score, 4)
    if best_item is None or rounded_score < confidence_threshold:
        return KnowledgeSearchResult.no_verified_answer(rounded_score)

    return KnowledgeSearchResult(
        answer=best_item.answer,
        confidence=rounded_score,
        source_id=best_item.id,
    )
