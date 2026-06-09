from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_organizations() -> list[dict]:
    return []
