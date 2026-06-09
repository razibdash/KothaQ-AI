from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.middleware.request_logging import log_backend_request

configure_logging(settings.LOG_LEVEL)
app = FastAPI(title=settings.APP_NAME)
app.middleware("http")(log_backend_request)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.APP_NAME}
