import logging
from uuid import UUID

from fastapi import APIRouter, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import DatabaseSession, ResolvedOrganization
from app.core.config import settings
from app.core.logging import get_logger, log_event, mask_phone_number
from app.models.conversation import Conversation
from app.services.storage import TenantStorageService
from app.services.telephony.twilio_adapter import (
    answer_twiml,
    caller_requests_handoff,
    greeting_twiml,
    handoff_twiml,
    retry_twiml,
)
from app.services.tenancy import OrganizationContext
from app.services.voice.orchestrator import VoiceOrchestrator

logger = get_logger(__name__)
router = APIRouter()


def _gather_url(org_slug: str) -> str:
    base = str(settings.PUBLIC_BASE_URL).rstrip("/")
    return f"{base}{settings.API_V1_PREFIX}/voice/gather/{org_slug}"


def _handoff_phone(organization: OrganizationContext) -> str | None:
    phone = organization.handoff_settings.get("phone_number")
    if isinstance(phone, str) and phone:
        return phone
    return settings.HUMAN_HANDOFF_FALLBACK_NUMBER


def _find_conversation(
    session: Session, organization_id: UUID, call_id: str
) -> Conversation | None:
    return session.scalar(
        select(Conversation).where(
            Conversation.organization_id == organization_id,
            Conversation.provider == "twilio",
            Conversation.provider_call_id == call_id,
        )
    )


def _xml(twiml: str) -> Response:
    return Response(content=twiml, media_type="application/xml")


@router.post("/incoming/{org_slug}")
async def incoming_call(
    org_slug: str,
    request: Request,
    organization: ResolvedOrganization,
    session: DatabaseSession,
) -> Response:
    call_id: str | None = None
    try:
        form = await request.form()
        call_id = str(form.get("CallSid") or request.headers.get("X-Call-ID") or "") or None
        caller_phone = str(form.get("From") or "") or None

        log_event(
            logger,
            logging.INFO,
            "incoming_call",
            tenant_id=organization.tenant_id,
            call_id=call_id,
            organization_slug=organization.slug,
            caller_phone=mask_phone_number(caller_phone),
        )

        storage = TenantStorageService(session, organization.id)
        conv = storage.create_conversation(
            provider="twilio",
            provider_call_id=call_id or f"noid-{org_slug}",
            caller_phone_masked=caller_phone,
            detected_language=organization.default_language,
        )
        storage.create_call_turn(
            conversation_id=conv.id,
            role="assistant",
            output_text=f"Greeting: {organization.name}",
        )
        session.commit()

        return _xml(
            greeting_twiml(
                org_name=organization.name,
                org_slug=org_slug,
                language_code=organization.default_language,
                gather_action_url=_gather_url(org_slug),
            )
        )
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "voice_call_error",
            tenant_id=organization.tenant_id,
            call_id=call_id,
            organization_slug=organization.slug,
            error_type=type(exc).__name__,
            operation="incoming_call",
        )
        raise


@router.post("/gather/{org_slug}")
async def gather_response(
    org_slug: str,
    request: Request,
    organization: ResolvedOrganization,
    session: DatabaseSession,
) -> Response:
    call_id: str | None = None
    try:
        form = await request.form()
        call_id = str(form.get("CallSid") or request.headers.get("X-Call-ID") or "") or None
        caller_phone = str(form.get("From") or "") or None
        speech_result = str(form.get("SpeechResult") or "").strip()

        gather_url = _gather_url(org_slug)
        language_code = organization.default_language
        storage = TenantStorageService(session, organization.id)

        # Resolve or create the conversation for this call
        conv = _find_conversation(session, organization.id, call_id or "") if call_id else None
        if conv is None:
            conv = storage.create_conversation(
                provider="twilio",
                provider_call_id=call_id or f"gather-{org_slug}",
                caller_phone_masked=caller_phone,
                detected_language=language_code,
            )

        # No speech captured — ask the caller to try again
        if not speech_result:
            log_event(
                logger,
                logging.INFO,
                "empty_speech_result",
                tenant_id=organization.tenant_id,
                call_id=call_id,
                organization_slug=organization.slug,
            )
            return _xml(retry_twiml(language_code, gather_url))

        # Explicit human-handoff request from caller
        if caller_requests_handoff(speech_result):
            log_event(
                logger,
                logging.INFO,
                "caller_requested_handoff",
                tenant_id=organization.tenant_id,
                call_id=call_id,
                organization_slug=organization.slug,
            )
            phone = _handoff_phone(organization)
            storage.create_handoff(
                conversation_id=conv.id,
                reason="caller_requested",
                target_number_masked=phone,
            )
            session.commit()
            return _xml(handoff_twiml(language_code, phone))

        # Process through the voice pipeline
        result = VoiceOrchestrator(session).handle_turn(
            organization,
            speech_result,
            call_id=call_id,
            conversation_id=conv.id,
        )

        storage.create_call_turn(
            conversation_id=conv.id,
            role="user",
            input_text=speech_result,
            output_text=result.response_text,
        )

        if result.should_handoff:
            phone = _handoff_phone(organization)
            storage.create_handoff(
                conversation_id=conv.id,
                reason="policy_required",
                target_number_masked=phone,
            )
            session.commit()
            return _xml(handoff_twiml(result.detected_language, phone))

        session.commit()
        return _xml(answer_twiml(result.response_text, result.detected_language, gather_url))

    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "voice_call_error",
            tenant_id=organization.tenant_id,
            call_id=call_id,
            organization_slug=organization.slug,
            error_type=type(exc).__name__,
            operation="gather_response",
        )
        raise


@router.post("/handoff/{org_slug}")
async def handoff_call(
    org_slug: str,
    request: Request,
    organization: ResolvedOrganization,
    session: DatabaseSession,
) -> Response:
    call_id: str | None = None
    try:
        form = await request.form()
        call_id = str(form.get("CallSid") or request.headers.get("X-Call-ID") or "") or None

        log_event(
            logger,
            logging.INFO,
            "handoff_call",
            tenant_id=organization.tenant_id,
            call_id=call_id,
            organization_slug=organization.slug,
        )

        phone = _handoff_phone(organization)
        conv = _find_conversation(session, organization.id, call_id or "") if call_id else None

        if conv:
            TenantStorageService(session, organization.id).create_handoff(
                conversation_id=conv.id,
                reason="handoff_webhook",
                target_number_masked=phone,
            )
            session.commit()

        return _xml(handoff_twiml(organization.default_language, phone))

    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "voice_call_error",
            tenant_id=organization.tenant_id,
            call_id=call_id,
            organization_slug=organization.slug,
            error_type=type(exc).__name__,
            operation="handoff_call",
        )
        raise
