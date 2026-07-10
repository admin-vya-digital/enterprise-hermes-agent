from pydantic import BaseModel, Field


class WriteMemoryRequest(BaseModel):
    content: str = Field(..., description="Conteúdo em Markdown a gravar como memória do contato.")
    filename: str = "perfil.md"
