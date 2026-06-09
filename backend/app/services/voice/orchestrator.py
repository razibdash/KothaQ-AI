import logging

from app.core.logging import get_logger, log_event
from app.services.ai.answer_policy import enforce_verified_answer_policy
from app.services.knowledge.search import search_knowledge
from app.services.language.router import detect_language_mode

logger = get_logger(__name__)


class VoiceOrchestrator:
    def handle_turn(
        self,
        organization_slug: str,
        caller_text: str,
        *,
        call_id: str | None = None,
    ) -> str:
        try:
            log_event(
                logger,
                logging.INFO,
                "user_input_received",
                tenant_id=organization_slug,
                call_id=call_id,
                input_length=len(caller_text),
            )

            language = detect_language_mode(caller_text)
            log_event(
                logger,
                logging.INFO,
                "language_detected",
                tenant_id=organization_slug,
                call_id=call_id,
                language=language,
            )

            result = search_knowledge(organization_slug, caller_text)
            confidence = float(result.get("confidence", 0.0))
            response, requires_handoff = enforce_verified_answer_policy(
                result.get("answer"),
                confidence,
            )
            log_event(
                logger,
                logging.INFO,
                "answer_selected",
                tenant_id=organization_slug,
                call_id=call_id,
                confidence=confidence,
                source_id=result.get("source_id"),
                requires_handoff=requires_handoff,
            )

            if requires_handoff:
                log_event(
                    logger,
                    logging.WARNING,
                    "unknown_question",
                    tenant_id=organization_slug,
                    call_id=call_id,
                    language=language,
                    input_length=len(caller_text),
                )
                log_event(
                    logger,
                    logging.INFO,
                    "handoff_requested",
                    tenant_id=organization_slug,
                    call_id=call_id,
                    reason="low_confidence",
                )

            return response
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "voice_turn_error",
                tenant_id=organization_slug,
                call_id=call_id,
                error_type=type(exc).__name__,
                operation="handle_turn",
            )
            raise
