from pydantic import BaseModel


class LeadRead(BaseModel):
    id: str | None = None
