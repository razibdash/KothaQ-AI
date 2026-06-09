import json
import logging
from io import StringIO

from app.core.logging import JsonFormatter, log_event, mask_phone_number


def test_mask_phone_number_preserves_only_last_four_digits() -> None:
    assert mask_phone_number("+880 1712-345678") == "*********5678"
    assert mask_phone_number("1234") == "****"
    assert mask_phone_number(None) is None


def test_structured_log_contains_context_and_redacts_secret_fields() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("tests.structured_logging")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    log_event(
        logger,
        logging.INFO,
        "incoming_call",
        tenant_id="tenant-demo",
        call_id="call-123",
        caller_phone="+15555550123",
        api_key="must-not-appear",
    )

    payload = json.loads(stream.getvalue())

    assert payload["event"] == "incoming_call"
    assert payload["tenant_id"] == "tenant-demo"
    assert payload["call_id"] == "call-123"
    assert payload["caller_phone"] == "*******0123"
    assert payload["api_key"] == "[REDACTED]"
    assert "must-not-appear" not in stream.getvalue()
