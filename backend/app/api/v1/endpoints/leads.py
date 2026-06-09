from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_leads() -> list[dict]:
    return []
