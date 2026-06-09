from uuid import UUID


def search_knowledge(organization_id: UUID, query: str) -> dict:
    return {"answer": None, "confidence": 0.0, "source_id": None}
