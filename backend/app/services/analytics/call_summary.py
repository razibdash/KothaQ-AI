"""Deterministic post-call summary generation.

Derives a structured summary from the records already written during the call
(CallTurn, UnknownQuestion, Lead, Handoff, Conversation) without requiring any
LLM or external call.

Outcome classification (highest priority first):
  handoff       — a human handoff was triggered
  lead_captured — lead status is 'new' (all mandatory fields captured), no handoff
  answered      — KB answers given, no unknowns, no handoff, no partial lead
  mixed         — both answered and unknown turns in the same call
  unknown       — no KB match found for any user utterance
  no_input      — caller connected but no user speech was processed
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.call_turn import CallTurn
from app.models.conversation import Conversation
from app.models.conversation_summary import ConversationSummary
from app.models.handoff import Handoff
from app.models.lead import Lead
from app.models.unknown_question import UnknownQuestion

# CallTurn output sentinels that are not real KB answers
_EXIT_SENTINEL = "[call ended by caller]"


@dataclass(frozen=True)
class SummaryResult:
    """In-memory summary; persisted via storage.save_conversation_summary()."""

    conversation_id: UUID
    organization_id: UUID
    outcome: str
    answered_count: int
    unanswered_count: int
    turn_count: int
    call_duration_seconds: int | None
    lead_interest: str | None
    lead_name: str | None
    lead_status: str | None
    handoff_reason: str | None
    follow_up_needed: bool


def _determine_outcome(
    *,
    answered_count: int,
    unanswered_count: int,
    lead: Lead | None,
    handoff_reason: str | None,
) -> str:
    if handoff_reason is not None:
        return "handoff"
    if lead is not None and lead.status == "new":
        return "lead_captured"
    if answered_count > 0 and unanswered_count == 0:
        return "answered"
    if answered_count > 0 and unanswered_count > 0:
        return "mixed"
    if unanswered_count > 0:
        return "unknown"
    return "no_input"


def summarize_conversation(
    session: Session,
    conversation_id: UUID,
    organization_id: UUID,
) -> SummaryResult:
    """Compute a deterministic summary from existing DB records for a conversation."""
    conv = session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == organization_id,
        )
    )
    if conv is None:
        raise ValueError(f"conversation {conversation_id} not found for org {organization_id}")

    # Count user speech turns (exclude greeting/system assistant turns)
    turn_count: int = session.scalar(  # type: ignore[assignment]
        select(func.count()).where(
            CallTurn.conversation_id == conversation_id,
            CallTurn.role == "user",
        )
    ) or 0

    # Unanswered = unknown questions raised during the call
    unanswered_count: int = session.scalar(  # type: ignore[assignment]
        select(func.count()).where(
            UnknownQuestion.conversation_id == conversation_id,
            UnknownQuestion.organization_id == organization_id,
        )
    ) or 0

    # Answered = user turns minus unknowns (each turn is either answered or not)
    answered_count = max(0, turn_count - unanswered_count)

    # Best lead for this conversation (prefer most-complete status)
    lead: Lead | None = session.scalar(
        select(Lead)
        .where(
            Lead.conversation_id == conversation_id,
            Lead.organization_id == organization_id,
        )
        .order_by(
            # "new" > "finalizing" > "collecting" — sort by status length DESC as proxy
            Lead.status.desc()
        )
        .limit(1)
    )

    # First handoff (if any)
    first_handoff: Handoff | None = session.scalar(
        select(Handoff)
        .where(
            Handoff.conversation_id == conversation_id,
            Handoff.organization_id == organization_id,
        )
        .order_by(Handoff.created_at)
        .limit(1)
    )

    handoff_reason = first_handoff.reason if first_handoff else None

    outcome = _determine_outcome(
        answered_count=answered_count,
        unanswered_count=unanswered_count,
        lead=lead,
        handoff_reason=handoff_reason,
    )

    duration: int | None = None
    if conv.started_at and conv.ended_at:
        from datetime import timezone as _tz

        def _utc(dt: datetime) -> datetime:
            return dt if dt.tzinfo else dt.replace(tzinfo=_tz.utc)

        duration = max(0, int((_utc(conv.ended_at) - _utc(conv.started_at)).total_seconds()))

    follow_up_needed = bool(
        handoff_reason is not None
        or unanswered_count > 0
        or (lead is not None and lead.status in ("collecting", "finalizing", "new"))
    )

    return SummaryResult(
        conversation_id=conversation_id,
        organization_id=organization_id,
        outcome=outcome,
        answered_count=answered_count,
        unanswered_count=unanswered_count,
        turn_count=turn_count,
        call_duration_seconds=duration,
        lead_interest=lead.interest if lead else None,
        lead_name=lead.name if lead else None,
        lead_status=lead.status if lead else None,
        handoff_reason=handoff_reason,
        follow_up_needed=follow_up_needed,
    )


def upsert_summary(
    session: Session,
    result: SummaryResult,
) -> ConversationSummary:
    """Persist (create or replace) a ConversationSummary from a SummaryResult."""
    existing = session.scalar(
        select(ConversationSummary).where(
            ConversationSummary.conversation_id == result.conversation_id,
        )
    )
    if existing is not None:
        existing.outcome = result.outcome
        existing.answered_count = result.answered_count
        existing.unanswered_count = result.unanswered_count
        existing.turn_count = result.turn_count
        existing.call_duration_seconds = result.call_duration_seconds
        existing.lead_interest = result.lead_interest
        existing.lead_name = result.lead_name
        existing.lead_status = result.lead_status
        existing.handoff_reason = result.handoff_reason
        existing.follow_up_needed = result.follow_up_needed
        session.flush()
        return existing

    summary = ConversationSummary(
        conversation_id=result.conversation_id,
        organization_id=result.organization_id,
        outcome=result.outcome,
        answered_count=result.answered_count,
        unanswered_count=result.unanswered_count,
        turn_count=result.turn_count,
        call_duration_seconds=result.call_duration_seconds,
        lead_interest=result.lead_interest,
        lead_name=result.lead_name,
        lead_status=result.lead_status,
        handoff_reason=result.handoff_reason,
        follow_up_needed=result.follow_up_needed,
    )
    session.add(summary)
    session.flush()
    return summary
