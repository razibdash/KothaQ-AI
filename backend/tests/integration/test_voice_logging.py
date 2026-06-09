import logging

from fastapi.testclient import TestClient
from pytest import LogCaptureFixture
from sqlalchemy.orm import Session

from app.api.v1.endpoints import voice
from app.core.logging import STRUCTURED_LOG_ATTR
from app.services.storage import create_organization


def test_incoming_call_logs_masked_caller_context(
    caplog: LogCaptureFixture,
    db_client: TestClient,
    db_session: Session,
) -> None:
    organization = create_organization(
        db_session,
        slug="tenant-demo",
        name="Tenant Demo",
    )
    db_session.commit()
    caplog.set_level(logging.INFO, logger=voice.__name__)

    response = db_client.post(
        "/api/v1/voice/incoming/tenant-demo",
        data={"CallSid": "call-123", "From": "+15555550123"},
    )

    incoming_event = next(
        getattr(record, STRUCTURED_LOG_ATTR)
        for record in caplog.records
        if getattr(record, STRUCTURED_LOG_ATTR, {}).get("event") == "incoming_call"
    )

    assert response.status_code == 200
    assert incoming_event == {
        "event": "incoming_call",
        "tenant_id": str(organization.id),
        "call_id": "call-123",
        "organization_slug": "tenant-demo",
        "caller_phone": "*******0123",
    }
    assert "+15555550123" not in caplog.text
