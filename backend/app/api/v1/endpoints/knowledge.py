from fastapi import APIRouter

from app.api.dependencies import ResolvedAPIOrganization

router = APIRouter()


@router.get("/")
def list_knowledge_items(organization: ResolvedAPIOrganization) -> list[dict]:
    return []
