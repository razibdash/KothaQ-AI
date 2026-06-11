from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.api.dependencies import DatabaseSession, ResolvedAPIOrganization
from app.services.storage import TenantStorageService

router = APIRouter()


class ConversationSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
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
    generated_at: datetime


@router.get("/")
def list_calls(organization: ResolvedAPIOrganization) -> list[dict]:
    return []


@router.get("/{conversation_id}/summary", response_model=ConversationSummaryRead)
def get_or_generate_call_summary(
    conversation_id: UUID,
    organization: ResolvedAPIOrganization,
    session: DatabaseSession,
) -> ConversationSummaryRead:
    """Return the summary for a conversation, generating it on demand if not yet stored."""
    storage = TenantStorageService(session, organization.id)
    summary = storage.get_conversation_summary(conversation_id)
    if summary is None:
        try:
            summary = storage.generate_conversation_summary(conversation_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        session.commit()
    return ConversationSummaryRead.model_validate(summary)
