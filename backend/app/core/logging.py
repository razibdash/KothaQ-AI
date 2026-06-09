import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.core.config import LogLevel

STRUCTURED_LOG_ATTR = "structured_log"
TALKQUE_HANDLER_ATTR = "talkque_handler"
REDACTED = "[REDACTED]"
SENSITIVE_KEY_PARTS = (
    "api_key",
    "authorization",
    "cookie",
    "credential",
    "password",
    "secret",
    "token",
)


def mask_phone_number(phone_number: str | None) -> str | None:
    if not phone_number:
        return None
    if "*" in phone_number:
        return phone_number

    digits = "".join(character for character in phone_number if character.isdigit())
    if not digits:
        return None
    if len(digits) <= 4:
        return "*" * len(digits)
    return f"{'*' * (len(digits) - 4)}{digits[-4:]}"


def _is_sensitive_key(key: str) -> bool:
    normalized_key = key.lower()
    return any(part in normalized_key for part in SENSITIVE_KEY_PARTS)


def _is_phone_key(key: str) -> bool:
    return "phone" in key.lower()


def _sanitize_value(key: str, value: Any) -> Any:
    if _is_sensitive_key(key):
        return REDACTED
    if _is_phone_key(key) and isinstance(value, str):
        return mask_phone_number(value)
    if isinstance(value, Mapping):
        return {
            str(nested_key): _sanitize_value(str(nested_key), nested_value)
            for nested_key, nested_value in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_value(key, item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        structured_data = getattr(record, STRUCTURED_LOG_ATTR, {})
        if isinstance(structured_data, Mapping):
            payload.update(
                {
                    str(key): _sanitize_value(str(key), value)
                    for key, value in structured_data.items()
                }
            )
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: LogLevel | str = LogLevel.INFO) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(str(level))

    for handler in root_logger.handlers:
        if getattr(handler, TALKQUE_HANDLER_ATTR, False):
            handler.setLevel(str(level))
            handler.setFormatter(JsonFormatter())
            return

    handler = logging.StreamHandler()
    setattr(handler, TALKQUE_HANDLER_ATTR, True)
    handler.setLevel(str(level))
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    *,
    tenant_id: str | None = None,
    call_id: str | None = None,
    **fields: Any,
) -> None:
    structured_data = {
        "event": event,
        "tenant_id": tenant_id,
        "call_id": call_id,
        **fields,
    }
    sanitized_data = {
        str(key): _sanitize_value(str(key), value)
        for key, value in structured_data.items()
    }
    logger.log(
        level,
        event,
        extra={STRUCTURED_LOG_ATTR: sanitized_data},
    )
