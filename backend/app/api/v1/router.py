from fastapi import APIRouter

from app.api.v1.admin.router import admin_router
from app.api.v1.endpoints import calls, health, knowledge, leads, organizations, unknown_questions, voice

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(calls.router, prefix="/calls", tags=["calls"])
api_router.include_router(leads.router, prefix="/leads", tags=["leads"])
api_router.include_router(voice.router, prefix="/voice", tags=["voice"])
api_router.include_router(
    unknown_questions.router,
    prefix="/unknown-questions",
    tags=["unknown-questions"],
)
api_router.include_router(admin_router)
