from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import mask_phone_number
from app.models.branch import Branch
from app.models.call_turn import CallTurn
from app.models.conversation import Conversation
from app.models.handoff import Handoff
from app.models.knowledge_item import KnowledgeItem
from app.models.lead import Lead
from app.models.organization import Organization
from app.models.phone_number import PhoneNumber
from app.models.unknown_question import UnknownQuestion


def create_organization(
    session: Session,
    *,
    slug: str,
    name: str,
    default_language: str = "bn-BD",
    supported_languages: list[str] | None = None,
    timezone: str = "Asia/Dhaka",
) -> Organization:
    organization = Organization(
        slug=slug,
        name=name,
        default_language=default_language,
        supported_languages=supported_languages or [default_language],
        timezone=timezone,
    )
    session.add(organization)
    session.flush()
    return organization


class TenantStorageService:
    def __init__(self, session: Session, organization_id: UUID) -> None:
        if not organization_id:
            raise ValueError("organization_id is required")
        self.session = session
        self.organization_id = organization_id

    def create_branch(
        self,
        *,
        slug: str,
        name: str,
        city: str | None = None,
        region: str | None = None,
        country: str | None = None,
        address: str | None = None,
        phone: str | None = None,
        timezone: str | None = None,
    ) -> Branch:
        branch = Branch(
            organization_id=self.organization_id,
            slug=slug,
            name=name,
            city=city,
            region=region,
            country=country,
            address=address,
            phone=phone,
            timezone=timezone,
        )
        self.session.add(branch)
        self.session.flush()
        return branch

    def create_phone_number(
        self,
        *,
        number_e164: str,
        provider: str,
        branch_id: UUID | None = None,
        provider_number_id: str | None = None,
        is_active: bool = True,
    ) -> PhoneNumber:
        self._require_owned_branch(branch_id)
        phone_number = PhoneNumber(
            organization_id=self.organization_id,
            branch_id=branch_id,
            number_e164=number_e164,
            provider=provider,
            provider_number_id=provider_number_id,
            is_active=is_active,
        )
        self.session.add(phone_number)
        self.session.flush()
        return phone_number

    def create_knowledge_item(
        self,
        *,
        question: str,
        answer: str,
        language: str,
        branch_id: UUID | None = None,
        tags: list[str] | None = None,
        status: str = "draft",
        source_type: str = "manual",
        source_reference: str | None = None,
    ) -> KnowledgeItem:
        self._require_owned_branch(branch_id)
        item = KnowledgeItem(
            organization_id=self.organization_id,
            branch_id=branch_id,
            question=question,
            answer=answer,
            language=language,
            tags=tags or [],
            status=status,
            source_type=source_type,
            source_reference=source_reference,
        )
        self.session.add(item)
        self.session.flush()
        return item

    def create_conversation(
        self,
        *,
        provider: str,
        provider_call_id: str,
        branch_id: UUID | None = None,
        caller_phone_masked: str | None = None,
        detected_language: str | None = None,
        status: str = "started",
    ) -> Conversation:
        self._require_owned_branch(branch_id)
        conversation = Conversation(
            organization_id=self.organization_id,
            branch_id=branch_id,
            provider=provider,
            provider_call_id=provider_call_id,
            caller_phone_masked=mask_phone_number(caller_phone_masked),
            detected_language=detected_language,
            status=status,
        )
        self.session.add(conversation)
        self.session.flush()
        return conversation

    def create_call_turn(
        self,
        *,
        conversation_id: UUID,
        role: str,
        input_text: str | None = None,
        normalized_text: str | None = None,
        output_text: str | None = None,
        confidence: float | None = None,
        intent: str | None = None,
    ) -> CallTurn:
        self._require_owned_conversation(conversation_id)
        turn = CallTurn(
            conversation_id=conversation_id,
            role=role,
            input_text=input_text,
            normalized_text=normalized_text,
            output_text=output_text,
            confidence=confidence,
            intent=intent,
        )
        self.session.add(turn)
        self.session.flush()
        return turn

    def create_unknown_question(
        self,
        *,
        question_text: str,
        conversation_id: UUID | None = None,
        normalized_text: str | None = None,
        detected_language: str | None = None,
        status: str = "new",
        suggested_answer: str | None = None,
    ) -> UnknownQuestion:
        self._require_owned_conversation(conversation_id)
        unknown_question = UnknownQuestion(
            organization_id=self.organization_id,
            conversation_id=conversation_id,
            question_text=question_text,
            normalized_text=normalized_text,
            detected_language=detected_language,
            status=status,
            suggested_answer=suggested_answer,
        )
        self.session.add(unknown_question)
        self.session.flush()
        return unknown_question

    def create_lead(
        self,
        *,
        name: str | None = None,
        phone_masked: str | None = None,
        interest: str | None = None,
        branch_id: UUID | None = None,
        conversation_id: UUID | None = None,
        callback_time: datetime | None = None,
        status: str = "new",
    ) -> Lead:
        self._require_owned_branch(branch_id)
        self._require_owned_conversation(conversation_id)
        lead = Lead(
            organization_id=self.organization_id,
            conversation_id=conversation_id,
            name=name,
            phone_masked=mask_phone_number(phone_masked),
            interest=interest,
            branch_id=branch_id,
            callback_time=callback_time,
            status=status,
        )
        self.session.add(lead)
        self.session.flush()
        return lead

    def create_handoff(
        self,
        *,
        conversation_id: UUID,
        reason: str,
        target_number_masked: str | None = None,
        status: str = "requested",
    ) -> Handoff:
        self._require_owned_conversation(conversation_id)
        handoff = Handoff(
            organization_id=self.organization_id,
            conversation_id=conversation_id,
            reason=reason,
            target_number_masked=mask_phone_number(target_number_masked),
            status=status,
        )
        self.session.add(handoff)
        self.session.flush()
        return handoff

    def list_knowledge_items(self) -> list[KnowledgeItem]:
        statement = select(KnowledgeItem).where(
            KnowledgeItem.organization_id == self.organization_id
        )
        return list(self.session.scalars(statement))

    def _require_owned_branch(self, branch_id: UUID | None) -> None:
        if branch_id is None:
            return
        statement = select(Branch.id).where(
            Branch.id == branch_id,
            Branch.organization_id == self.organization_id,
        )
        if self.session.scalar(statement) is None:
            raise ValueError("branch does not belong to organization")

    def _require_owned_conversation(self, conversation_id: UUID | None) -> None:
        if conversation_id is None:
            return
        statement = select(Conversation.id).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == self.organization_id,
        )
        if self.session.scalar(statement) is None:
            raise ValueError("conversation does not belong to organization")
