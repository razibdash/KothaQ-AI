import logging
from html import escape

from fastapi import APIRouter, Request, Response

from app.api.dependencies import ResolvedOrganization
from app.core.logging import get_logger, log_event, mask_phone_number

logger = get_logger(__name__)
router = APIRouter()


@router.post("/incoming/{org_slug}")
async def incoming_call(
    org_slug: str,
    request: Request,
    organization: ResolvedOrganization,
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

        # Replace with verified provider routing and voice orchestration.
        xml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Response>
  <Say>Welcome to {escape(organization.name)}. Voice agent setup is ready.</Say>
</Response>
"""
        return Response(content=xml, media_type="application/xml")
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
