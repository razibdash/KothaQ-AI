from pydantic import BaseModel


class OrganizationRead(BaseModel):
    id: str | None = None
