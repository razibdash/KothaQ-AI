from fastapi import APIRouter

from app.api.dependencies import ResolvedAPIOrganization

router = APIRouter()


@router.get("/")
def list_leads(organization: ResolvedAPIOrganization) -> list[dict]:
    return []
