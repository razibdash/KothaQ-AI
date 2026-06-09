from pydantic import BaseModel


class VoiceTurnRequest(BaseModel):
    id: str | None = None
