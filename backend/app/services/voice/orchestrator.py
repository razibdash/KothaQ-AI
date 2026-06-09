import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.services.ai.answer_policy import enforce_verified_answer_policy
from app.services.knowledge.search import search_knowledge
from app.services.language.language_router import choose_response_language
from app.services.tenancy import OrganizationContext
from app.services.voice.response_style import (
    ResponseStyle,
    caller_requests_details,
    style_verified_answer,
    unknown_answer_fallback,
)

logger = get_logger(__name__)


class VoiceOrchestrator:
    def __init__(self, session: Session) -> None:
        """Create a voice orchestrator backed by the current database session."""
        self.session = session

    def handle_turn(
        self,
        organization: OrganizationContext,
        caller_text: str,
        *,
        call_id: str | None = None,
        branch_id: UUID | None = None,
        response_style: ResponseStyle = "student_friendly",
    ) -> str:
        """Handle one tenant-scoped caller turn and return a styled voice reply."""
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
            confidence = result.confidence
            response, requires_handoff = enforce_verified_answer_policy(
                result.answer,
                confidence,
            )
            if requires_handoff:
                response = unknown_answer_fallback(language, response_style)
            else:
                response = style_verified_answer(
                    response,
                    language,
                    response_style,
                    include_details=caller_requests_details(caller_text),
                )
            log_event(
                logger,
                logging.INFO,
                "answer_selected",
                tenant_id=organization.tenant_id,
                call_id=call_id,
                organization_slug=organization.slug,
                confidence=confidence,
                source_id=result.source_id,
                requires_handoff=requires_handoff,
            )

            if requires_handoff:
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
                log_event(
                    logger,
                    logging.INFO,
                    "handoff_requested",
                    tenant_id=organization.tenant_id,
                    call_id=call_id,
                    organization_slug=organization.slug,
                    reason="low_confidence",
                )

            return response
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
