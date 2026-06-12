from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import mask_phone_number
from app.models.branch import Branch
from app.models.call_turn import CallTurn
from app.models.conversation import Conversation
from app.models.conversation_summary import ConversationSummary
from app.models.handoff import Handoff
from app.models.knowledge_item import KnowledgeItem
from app.models.lead import Lead
from app.models.organization import Organization
from app.models.phone_number import PhoneNumber
from app.models.unknown_question import UnknownQuestion

_ACTIVE_LEAD_STATUSES = ("collecting", "finalizing")


def list_organizations(session: Session) -> list[Organization]:
    """Return all organizations ordered by name — admin use only."""
    return list(session.scalars(select(Organization).order_by(Organization.name)))


def get_organization_by_slug(session: Session, slug: str) -> Organization | None:
    """Return a single Organization by slug, or None — admin use only."""
    return session.scalar(select(Organization).where(Organization.slug == slug))


def create_organization(
    session: Session,
    *,
    slug: str,
    name: str,
    default_language: str = "bn-BD",
    supported_languages: list[str] | None = None,
    timezone: str = "Asia/Dhaka",
    handoff_settings: dict[str, object] | None = None,
) -> Organization:
    organization = Organization(
        slug=slug,
        name=name,
        default_language=default_language,
        supported_languages=supported_languages or [default_language],
        timezone=timezone,
        handoff_settings=handoff_settings or {},
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

    def complete_conversation(self, conversation_id: UUID) -> None:
        """Mark a conversation as completed, record its end time, and generate a summary."""
        from app.services.analytics.call_summary import summarize_conversation, upsert_summary

        conv = self.session.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.organization_id == self.organization_id,
            )
        )
        if conv is not None:
            conv.status = "completed"
            conv.ended_at = datetime.now(timezone.utc)
            self.session.flush()
            result = summarize_conversation(self.session, conversation_id, self.organization_id)
            upsert_summary(self.session, result)

    def generate_conversation_summary(self, conversation_id: UUID) -> ConversationSummary:
        """Compute and persist a summary on demand (for already-completed conversations)."""
        from app.services.analytics.call_summary import summarize_conversation, upsert_summary

        self._require_owned_conversation(conversation_id)
        result = summarize_conversation(self.session, conversation_id, self.organization_id)
        return upsert_summary(self.session, result)

    def get_conversation_summary(self, conversation_id: UUID) -> ConversationSummary | None:
        """Return the persisted summary for a conversation, or None if not yet generated."""
        return self.session.scalar(
            select(ConversationSummary).where(
                ConversationSummary.conversation_id == conversation_id,
                ConversationSummary.organization_id == self.organization_id,
            )
        )

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

    def mark_unknown_question_ignored(self, uq_id: UUID) -> UnknownQuestion:
        uq = self._get_owned_unknown_question(uq_id)
        if uq is None:
            raise ValueError("unknown question not found")
        uq.status = "ignored"
        self.session.flush()
        return uq

    def approve_unknown_question(
        self,
        uq_id: UUID,
        *,
        approved_answer: str,
        question_override: str | None = None,
        language: str | None = None,
        tags: list[str] | None = None,
    ) -> tuple[UnknownQuestion, KnowledgeItem]:
        uq = self._get_owned_unknown_question(uq_id)
        if uq is None:
            raise ValueError("unknown question not found")
        if uq.status == "approved":
            raise ValueError("unknown question is already approved")
        kb_item = self.create_knowledge_item(
            question=question_override or uq.question_text,
            answer=approved_answer,
            language=language or uq.detected_language or "bn-BD",
            tags=tags or [],
            status="approved",
            source_type="unknown_question_approval",
            source_reference=str(uq_id),
        )
        uq.status = "approved"
        uq.suggested_answer = approved_answer
        self.session.flush()
        return uq, kb_item

    def list_unknown_questions(
        self,
        *,
        status: str | None = None,
    ) -> list[UnknownQuestion]:
        statement = select(UnknownQuestion).where(
            UnknownQuestion.organization_id == self.organization_id
        )
        if status is not None:
            statement = statement.where(UnknownQuestion.status == status)
        statement = statement.order_by(UnknownQuestion.created_at.desc())
        return list(self.session.scalars(statement))

    def _get_owned_unknown_question(self, uq_id: UUID) -> UnknownQuestion | None:
        return self.session.scalar(
            select(UnknownQuestion).where(
                UnknownQuestion.id == uq_id,
                UnknownQuestion.organization_id == self.organization_id,
            )
        )

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

    def get_active_lead(self, conversation_id: UUID) -> Lead | None:
        """Return the in-progress lead (collecting or finalizing) for a conversation."""
        return self.session.scalar(
            select(Lead).where(
                Lead.organization_id == self.organization_id,
                Lead.conversation_id == conversation_id,
                Lead.status.in_(_ACTIVE_LEAD_STATUSES),
            )
        )

    def upsert_collecting_lead(
        self,
        *,
        conversation_id: UUID,
        interest: str | None = None,
        name: str | None = None,
        phone_masked: str | None = None,
    ) -> Lead:
        """Create or update the collecting lead for a conversation.

        Only updates fields that are currently None in the DB record so that
        partial captures from earlier turns are never overwritten.
        """
        self._require_owned_conversation(conversation_id)
        lead = self.get_active_lead(conversation_id)
        if lead is None:
            conv = self.session.scalar(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            initial_phone = phone_masked or (conv.caller_phone_masked if conv else None)
            lead = Lead(
                organization_id=self.organization_id,
                conversation_id=conversation_id,
                phone_masked=initial_phone,
                status="collecting",
            )
            self.session.add(lead)
            self.session.flush()
        if interest is not None and lead.interest is None:
            lead.interest = interest
        if name is not None and lead.name is None:
            lead.name = name
        if phone_masked is not None and lead.phone_masked is None:
            lead.phone_masked = mask_phone_number(phone_masked)
        self.session.flush()
        return lead

    def set_lead_status(self, lead_id: UUID, status: str) -> None:
        """Transition a lead to the given status."""
        lead = self.session.scalar(
            select(Lead).where(
                Lead.id == lead_id,
                Lead.organization_id == self.organization_id,
            )
        )
        if lead is not None:
            lead.status = status
            self.session.flush()

    def finalize_lead(self, lead_id: UUID, *, callback_notes: str | None = None) -> None:
        """Mark a lead complete (status='new') and persist any callback preference."""
        lead = self.session.scalar(
            select(Lead).where(
                Lead.id == lead_id,
                Lead.organization_id == self.organization_id,
            )
        )
        if lead is not None:
            lead.status = "new"
            if callback_notes is not None:
                lead.callback_notes = callback_notes
            self.session.flush()

    # ── Branch admin ─────────────────────────────────────────────────────────

    def list_branches(self) -> list[Branch]:
        """Return all branches for this organization ordered by name."""
        return list(
            self.session.scalars(
                select(Branch)
                .where(Branch.organization_id == self.organization_id)
                .order_by(Branch.name)
            )
        )

    def get_branch(self, branch_id: UUID) -> Branch | None:
        """Return a branch owned by this organization, or None."""
        return self.session.scalar(
            select(Branch).where(
                Branch.id == branch_id,
                Branch.organization_id == self.organization_id,
            )
        )

    def update_branch(self, branch_id: UUID, updates: dict) -> Branch:
        """Apply ``updates`` dict to the branch.  Raises ValueError if not found."""
        branch = self.get_branch(branch_id)
        if branch is None:
            raise ValueError("branch not found")
        for key, value in updates.items():
            setattr(branch, key, value)
        self.session.flush()
        return branch

    # ── Knowledge item admin ──────────────────────────────────────────────────

    def get_knowledge_item(self, item_id: UUID) -> KnowledgeItem | None:
        """Return a knowledge item owned by this organization, or None."""
        return self.session.scalar(
            select(KnowledgeItem).where(
                KnowledgeItem.id == item_id,
                KnowledgeItem.organization_id == self.organization_id,
            )
        )

    def update_knowledge_item(self, item_id: UUID, updates: dict) -> KnowledgeItem:
        """Apply ``updates`` dict to the knowledge item.  Raises ValueError if not found."""
        item = self.get_knowledge_item(item_id)
        if item is None:
            raise ValueError("knowledge item not found")
        for key, value in updates.items():
            setattr(item, key, value)
        self.session.flush()
        return item

    def set_knowledge_item_status(self, item_id: UUID, new_status: str) -> KnowledgeItem:
        """Transition a knowledge item to ``new_status``.  Raises ValueError if not found."""
        item = self.get_knowledge_item(item_id)
        if item is None:
            raise ValueError("knowledge item not found")
        item.status = new_status
        self.session.flush()
        return item

    def _require_owned_conversation(self, conversation_id: UUID | None) -> None:
        if conversation_id is None:
            return
        statement = select(Conversation.id).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == self.organization_id,
        )
        if self.session.scalar(statement) is None:
            raise ValueError("conversation does not belong to organization")
