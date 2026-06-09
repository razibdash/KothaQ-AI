from fastapi import APIRouter, Request, Response

router = APIRouter()


@router.post("/incoming/{organization_slug}")
async def incoming_call(organization_slug: str, request: Request) -> Response:
    # Replace with TwiML/telephony adapter implementation.
    xml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Response>
  <Say>Welcome to {organization_slug}. Voice agent setup is ready.</Say>
</Response>
"""
    return Response(content=xml, media_type="application/xml")
