from pydantic import BaseModel


class KnowledgeItemRead(BaseModel):
    id: str | None = None
