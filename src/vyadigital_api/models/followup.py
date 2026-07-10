from typing import Optional

from pydantic import BaseModel, Field


class FollowupRequest(BaseModel):
    name: str
    schedule: str = Field(..., description="Cron ('0 9 * * *'), intervalo ('2h', '30m', '1d') ou ISO one-shot.")
    prompt: str
    repeat: Optional[int] = Field(None, description="Número máximo de execuções. Vazio = indefinido.")
