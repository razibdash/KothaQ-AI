import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.services.ai.answer_policy import AnswerPolicyCandidate, evaluate_answer_policy
from app.services.knowledge.search import normalize_search_text, search_knowledge
from app.services.language.language_router import choose_response_language, detect_language
from app.services.leads.capture import (
    LeadFields,
    apply_extraction,
    callback_question,
    extract_callback_time,
    is_lead_complete,
    next_lead_question,
)
from app.services.leads.intent import detect_lead_intent
from app.services.storage import TenantStorageService
from app.services.tenancy import OrganizationContext
from app.services.voice.response_style import (
    ResponseStyle,
    caller_requests_details,
    style_verified_answer,
    unknown_answer_fallback,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class VoiceTurnResult:
    """Return value of VoiceOrchestrator.handle_turn."""

    response_text: str
    should_handoff: bool
    detected_language: str


class VoiceOrchestrator:
    def __init__(self, session: Session) -> None:
        self.session = session

    def handle_turn(
        self,
        organization: OrganizationContext,
        caller_text: str,
        *,
        call_id: str | None = None,
        branch_id: UUID | None = None,
        conversation_id: UUID | None = None,
        response_style: ResponseStyle = "student_friendly",
    ) -> VoiceTurnResult:
        """Handle one tenant-scoped caller turn and return a structured voice reply."""
        try:
            log_event(
                logger,
                logging.INFO,
                "user_input_received",
                tenant_id=organization.tenant_id,
                call_id=call_id,
                organization_slug=organization.slug,
                input_length=len(caller_text),
            )

            language = choose_response_language(
                caller_text,
                organization.default_language,
                organization.supported_languages,
            )
            log_event(
                logger,
                logging.INFO,
                "language_detected",
                tenant_id=organization.tenant_id,
                call_id=call_id,
                organization_slug=organization.slug,
                language=language,
            )

            result = search_knowledge(
                self.session,
                organization.id,
                caller_text,
                branch_id=branch_id,
            )
            normalized_text = normalize_search_text(caller_text)
            candidate = AnswerPolicyCandidate(
                item=result.source_item,
                confidence=result.confidence,
            )
            policy = evaluate_answer_policy(
                caller_text,
                normalized_text,
                organization.id,
                candidate,
                branch_id=branch_id,
            )

            if policy.answer_allowed:
                response = style_verified_answer(
                    policy.response_text,
                    language,
                    response_style,
                    include_details=caller_requests_details(caller_text),
                )
            else:
                response = unknown_answer_fallback(language, response_style)

            # ------------------------------------------------------------------
            # Lead capture — runs alongside FAQ; at most one question per turn
            # ------------------------------------------------------------------
            lead_follow_up: str | None = None
            if conversation_id is not None:
                storage = TenantStorageService(self.session, organization.id)
                active_lead = storage.get_active_lead(conversation_id)
                intent = detect_lead_intent(caller_text)

                if active_lead is not None and active_lead.status == "finalizing":
                    # Caller is responding to the callback-time question
                    callback_notes = extract_callback_time(caller_text)
                    storage.finalize_lead(active_lead.id, callback_notes=callback_notes)
                    log_event(
                        logger,
                        logging.INFO,
                        "lead_finalized",
                        tenant_id=organization.tenant_id,
                        call_id=call_id,
                        organization_slug=organization.slug,
                    )
                elif active_lead is not None or intent is not None:
                    # Either continuing an in-progress lead or starting a new one
                    current_fields = LeadFields(
                        interest=active_lead.interest if active_lead else None,
                        name=active_lead.name if active_lead else None,
                        phone_masked=active_lead.phone_masked if active_lead else None,
                    )
                    effective_intent = intent or "general"
                    updated_fields = apply_extraction(current_fields, caller_text, effective_intent)

                    # Fall back to the intent label itself when no noun phrase extracted
                    if updated_fields.interest is None and intent is not None:
                        updated_fields = LeadFields(
                            interest=intent,
                            name=updated_fields.name,
                            phone_masked=updated_fields.phone_masked,
                        )

                    upserted = storage.upsert_collecting_lead(
                        conversation_id=conversation_id,
                        interest=updated_fields.interest,
                        name=updated_fields.name,
                        phone_masked=updated_fields.phone_masked,
                    )
                    log_event(
                        logger,
                        logging.INFO,
                        "lead_updated",
                        tenant_id=organization.tenant_id,
                        call_id=call_id,
                        organization_slug=organization.slug,
                        lead_id=str(upserted.id),
                    )

                    if is_lead_complete(updated_fields):
                        # Check if callback time was also given in this same utterance
                        callback_notes = extract_callback_time(caller_text)
                        if callback_notes:
                            storage.finalize_lead(upserted.id, callback_notes=callback_notes)
                            log_event(
                                logger,
                                logging.INFO,
                                "lead_finalized",
                                tenant_id=organization.tenant_id,
                                call_id=call_id,
                                organization_slug=organization.slug,
                            )
                        else:
                            # Transition to finalizing; ask callback question if not handing off
                            storage.set_lead_status(upserted.id, "finalizing")
                            if not policy.should_handoff:
                                lead_follow_up = callback_question(language)
                    elif not policy.should_handoff:
                        lead_follow_up = next_lead_question(updated_fields, language)

            if lead_follow_up:
                response = f"{response} {lead_follow_up}"

            log_event(
                logger,
                logging.INFO,
                "answer_selected",
                tenant_id=organization.tenant_id,
                call_id=call_id,
                organization_slug=organization.slug,
                confidence=policy.confidence,
                source_id=policy.source_knowledge_item_id,
                requires_handoff=policy.should_handoff,
            )

            if policy.should_log_unknown:
                TenantStorageService(self.session, organization.id).create_unknown_question(
                    question_text=caller_text,
                    conversation_id=conversation_id,
                    normalized_text=normalized_text,
                    detected_language=detect_language(caller_text),
                )
                log_event(
                    logger,
                    logging.WARNING,
                    "unknown_question",
                    tenant_id=organization.tenant_id,
                    call_id=call_id,
                    organization_slug=organization.slug,
                    language=language,
                    input_length=len(caller_text),
                )

            if policy.should_handoff:
                log_event(
                    logger,
                    logging.INFO,
                    "handoff_requested",
                    tenant_id=organization.tenant_id,
                    call_id=call_id,
                    organization_slug=organization.slug,
                    reason=policy.reason,
                )

            return VoiceTurnResult(
                response_text=response,
                should_handoff=policy.should_handoff,
                detected_language=language,
            )
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "voice_turn_error",
                tenant_id=organization.tenant_id,
                call_id=call_id,
                organization_slug=organization.slug,
                error_type=type(exc).__name__,
                operation="handle_turn",
            )
            raise
