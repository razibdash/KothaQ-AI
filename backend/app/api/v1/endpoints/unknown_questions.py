from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict

from app.api.dependencies import DatabaseSession, ResolvedAPIOrganization
from app.services.storage import TenantStorageService

router = APIRouter()


class UnknownQuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    question_text: str
    normalized_text: str | None
    detected_language: str | None
    status: str
    suggested_answer: str | None
    conversation_id: UUID | None
    created_at: datetime


class ApproveUnknownQuestionRequest(BaseModel):
    answer: str
    question_override: str | None = None
    language: str | None = None
    tags: list[str] | None = None


class ApprovalResult(BaseModel):
    unknown_question_id: UUID
    status: str
    knowledge_item_id: UUID


@router.get("/", response_model=list[UnknownQuestionRead])
def list_unknown_questions(
    organization: ResolvedAPIOrganization,
    session: DatabaseSession,
    filter_status: str | None = Query(default=None, alias="status"),
) -> list[UnknownQuestionRead]:
    """List unknown questions for the resolved organization, optionally filtered by status."""
    storage = TenantStorageService(session, organization.id)
    items = storage.list_unknown_questions(status=filter_status)
    return [UnknownQuestionRead.model_validate(item) for item in items]


@router.patch("/{uq_id}/ignore", response_model=UnknownQuestionRead)
def ignore_unknown_question(
    uq_id: UUID,
    organization: ResolvedAPIOrganization,
    session: DatabaseSession,
) -> UnknownQuestionRead:
    """Mark an unknown question as ignored so it does not appear in new-question queues."""
    storage = TenantStorageService(session, organization.id)
    try:
        uq = storage.mark_unknown_question_ignored(uq_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    session.commit()
    return UnknownQuestionRead.model_validate(uq)


@router.post("/{uq_id}/approve", response_model=ApprovalResult)
def approve_unknown_question(
    uq_id: UUID,
    body: ApproveUnknownQuestionRequest,
    organization: ResolvedAPIOrganization,
    session: DatabaseSession,
) -> ApprovalResult:
    """Approve an unknown question with a verified answer, creating a searchable KB entry."""
    storage = TenantStorageService(session, organization.id)
    try:
        uq, kb_item = storage.approve_unknown_question(
            uq_id,
            approved_answer=body.answer,
            question_override=body.question_override,
            language=body.language,
            tags=body.tags,
        )
    except ValueError as exc:
        detail = str(exc)
        http_status = (
            status.HTTP_409_CONFLICT
            if "already approved" in detail
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=http_status, detail=detail) from exc
    session.commit()
    return ApprovalResult(
        unknown_question_id=uq.id,
        status=uq.status,
        knowledge_item_id=kb_item.id,
    )
