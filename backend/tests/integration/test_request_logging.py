import logging

from fastapi.testclient import TestClient
from pytest import LogCaptureFixture

from app.core.logging import STRUCTURED_LOG_ATTR
from app.main import app
from app.middleware import request_logging


def test_backend_request_log_includes_available_context(
    caplog: LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger=request_logging.__name__)
    client = TestClient(app)

    response = client.get(
        "/health",
        headers={"X-Tenant-ID": "tenant-demo", "X-Call-ID": "call-123"},
    )

    request_event = next(
        getattr(record, STRUCTURED_LOG_ATTR)
        for record in caplog.records
        if getattr(record, STRUCTURED_LOG_ATTR, {}).get("event")
        == "backend_request_completed"
    )

    assert response.status_code == 200
    assert request_event["tenant_id"] == "tenant-demo"
    assert request_event["call_id"] == "call-123"
    assert request_event["method"] == "GET"
    assert request_event["path"] == "/health"
    assert request_event["status_code"] == 200
    assert request_event["duration_ms"] >= 0
