import logging
from collections.abc import Awaitable, Callable
from time import perf_counter

from fastapi import Request, Response

from app.core.logging import get_logger, log_event

logger = get_logger(__name__)


async def log_backend_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    started_at = perf_counter()
    tenant_id = request.headers.get("X-Tenant-ID")
    call_id = request.headers.get("X-Call-ID")

    try:
        response = await call_next(request)
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "backend_request_error",
            tenant_id=tenant_id,
            call_id=call_id,
            method=request.method,
            path=request.url.path,
            duration_ms=round((perf_counter() - started_at) * 1000, 2),
            error_type=type(exc).__name__,
        )
        raise

    log_event(
        logger,
        logging.INFO,
        "backend_request_completed",
        tenant_id=tenant_id,
        call_id=call_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )
    return response
