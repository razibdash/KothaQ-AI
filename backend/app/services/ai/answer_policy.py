"""Verified-answer policy for tenant-scoped voice agent replies.

This module is the single authority on whether a candidate answer may be
spoken to a caller.  It does not style replies — that is the responsibility
of app.services.voice.response_style.

Confidence tiers and decision rules:
  HIGH  (>= 0.80) + approved source                   → answer verbatim
  MEDIUM (0.65–0.79) + non-sensitive + approved source → answer with hedge
  MEDIUM + sensitive topic                             → deny (require human)
  LOW   (< 0.65)                                       → deny, log, handoff
  Any   + unapproved source                            → deny
  Any   + cross-tenant source                          → deny (security event)
  No candidate                                         → deny, log, handoff
"""

from dataclasses import dataclass
from uuid import UUID

from app.models.knowledge_item import KnowledgeItem

HIGH_CONFIDENCE_THRESHOLD = 0.80
MEDIUM_CONFIDENCE_THRESHOLD = 0.65  # aligned with search.VERIFIED_CONFIDENCE_THRESHOLD

# Tokens in *normalised* caller text (already mapped to English concepts by the
# language router) that indicate topics where an approved, high-confidence source
# is strictly required before answering.
SENSITIVE_KEYWORDS = frozenset(
    {
        "fee",
        "cost",
        "tuition",
        "payment",
        "deadline",
        "legal",
        "medical",
    }
)

_MEDIUM_HEDGE = "Based on available information: "
_HANDOFF_TEXT = (
    "I am not fully sure about this information. "
    "I can connect you to a human representative."
)


@dataclass(frozen=True)
class AnswerPolicyCandidate:
    """Knowledge item and its search confidence returned by the knowledge search stage."""

    item: KnowledgeItem | None
    confidence: float


@dataclass(frozen=True)
class AnswerPolicyResult:
    answer_allowed: bool
    response_text: str
    confidence: float
    reason: str
    source_knowledge_item_id: UUID | None
    should_handoff: bool
    should_log_unknown: bool


def _deny(
    confidence: float,
    reason: str,
    source_id: UUID | None = None,
    *,
    should_log_unknown: bool,
) -> AnswerPolicyResult:
    return AnswerPolicyResult(
        answer_allowed=False,
        response_text=_HANDOFF_TEXT,
        confidence=confidence,
        reason=reason,
        source_knowledge_item_id=source_id,
        should_handoff=True,
        should_log_unknown=should_log_unknown,
    )


def _allow(
    item: KnowledgeItem,
    confidence: float,
    reason: str,
    *,
    hedge: bool = False,
) -> AnswerPolicyResult:
    text = f"{_MEDIUM_HEDGE}{item.answer}" if hedge else item.answer
    return AnswerPolicyResult(
        answer_allowed=True,
        response_text=text,
        confidence=confidence,
        reason=reason,
        source_knowledge_item_id=item.id,
        should_handoff=False,
        should_log_unknown=False,
    )


def _is_sensitive(normalized_text: str) -> bool:
    return bool(set(normalized_text.casefold().split()) & SENSITIVE_KEYWORDS)


def evaluate_answer_policy(
    caller_text: str,
    normalized_text: str,
    organization_id: UUID,
    candidate: AnswerPolicyCandidate,
    *,
    branch_id: UUID | None = None,
) -> AnswerPolicyResult:
    """Apply the verified-answer policy and return a structured decision.

    Parameters
    ----------
    caller_text:     Raw text from the caller (used for logging context only).
    normalized_text: Language-router output used for sensitive-topic detection.
    organization_id: Requesting tenant — the source item must belong to this org.
    candidate:       Best knowledge item and its confidence score from search.
    branch_id:       Optional branch scope (passed through for future use).
    """
    confidence = candidate.confidence
    item = candidate.item

    # 1. No candidate returned by knowledge search
    if item is None:
        return _deny(confidence, "no_candidate", should_log_unknown=True)

    # 2. Cross-tenant guard — item must belong to the requesting org
    if item.organization_id != organization_id:
        return _deny(0.0, "cross_tenant_source", should_log_unknown=False)

    # 3. Low confidence — unknown question, cannot answer reliably
    if confidence < MEDIUM_CONFIDENCE_THRESHOLD:
        return _deny(confidence, "low_confidence", should_log_unknown=True)

    # 4. All answers require an approved source (defense-in-depth;
    #    the search service already filters by status="approved", but a direct
    #    policy call — e.g. in tests — must not bypass this check)
    if item.status != "approved":
        sensitive = _is_sensitive(normalized_text)
        reason = "sensitive_topic_unapproved_source" if sensitive else "unapproved_source"
        return _deny(confidence, reason, source_id=item.id, should_log_unknown=False)

    sensitive = _is_sensitive(normalized_text)

    # 5. Medium confidence: only non-sensitive queries may be answered with a hedge
    if confidence < HIGH_CONFIDENCE_THRESHOLD:
        if sensitive:
            return _deny(
                confidence,
                "sensitive_topic_medium_confidence",
                source_id=item.id,
                should_log_unknown=False,
            )
        return _allow(item, confidence, "medium_confidence_approved", hedge=True)

    # 6. High confidence + approved source → answer verbatim
    return _allow(item, confidence, "high_confidence_approved")
