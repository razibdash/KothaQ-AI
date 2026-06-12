"""Semantic similarity search over tenant-scoped knowledge items.

Flow per search call:
  1. Embed the caller's query with the configured embedding model.
  2. For each approved knowledge item that has a stored embedding, compute
     cosine similarity against the query embedding.
  3. Items without a stored embedding are embedded on-the-fly and persisted
     so subsequent searches are faster (lazy warm-up).
  4. Return the highest-scoring item if it clears the confidence threshold,
     otherwise return a no-answer result.

This module is only entered when is_semantic_available() is True.  The
caller (search.py) handles the fallback to fuzzy search.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge_item import KnowledgeItem
from app.services.ai.embeddings import cosine_similarity, embed_text, embed_texts
from app.services.knowledge.search import KnowledgeSearchResult, VERIFIED_CONFIDENCE_THRESHOLD


def _ensure_embeddings(session: Session, items: list[KnowledgeItem]) -> None:
    """Generate and persist embeddings for any items that don't have one yet."""
    missing = [item for item in items if item.question_embedding is None]
    if not missing:
        return
    texts = [item.question for item in missing]
    vectors = embed_texts(texts)
    for item, vector in zip(missing, vectors):
        item.question_embedding = vector
    session.flush()


def semantic_search(
    session: Session,
    items: list[KnowledgeItem],
    query: str,
    confidence_threshold: float = VERIFIED_CONFIDENCE_THRESHOLD,
) -> KnowledgeSearchResult:
    """Find the best knowledge item for *query* using cosine similarity.

    Parameters
    ----------
    session:              Active SQLAlchemy session (used for lazy embedding writes).
    items:                Pre-filtered approved items scoped to the requesting tenant.
    query:                Raw caller text (not pre-normalised — embedding handles it).
    confidence_threshold: Minimum cosine similarity to return a result.
    """
    if not items:
        return KnowledgeSearchResult.no_verified_answer()

    _ensure_embeddings(session, items)

    query_vector = embed_text(query)

    best_item: KnowledgeItem | None = None
    best_score = 0.0
    for item in items:
        if item.question_embedding is None:
            continue
        score = cosine_similarity(query_vector, item.question_embedding)
        if score > best_score:
            best_item = item
            best_score = score

    rounded = round(best_score, 4)
    if best_item is None or rounded < confidence_threshold:
        return KnowledgeSearchResult.no_verified_answer(rounded)

    return KnowledgeSearchResult(
        answer=best_item.answer,
        confidence=rounded,
        source_id=best_item.id,
        source_item=best_item,
    )


def embed_and_store(session: Session, organization_id: UUID, item_id: UUID) -> None:
    """Eagerly embed a single knowledge item by ID.

    Call this after creating or updating a knowledge item so the embedding is
    ready before the first search call.
    """
    item = session.scalar(
        select(KnowledgeItem).where(
            KnowledgeItem.id == item_id,
            KnowledgeItem.organization_id == organization_id,
        )
    )
    if item is None:
        return
    item.question_embedding = embed_text(item.question)
    session.flush()
