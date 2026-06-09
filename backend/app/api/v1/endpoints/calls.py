from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_calls() -> list[dict]:
    return []
