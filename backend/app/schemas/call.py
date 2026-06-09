from pydantic import BaseModel


class CallRead(BaseModel):
    id: str | None = None
