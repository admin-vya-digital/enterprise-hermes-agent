from pydantic import BaseModel, Field


class KnowledgeUrlRequest(BaseModel):
    url: str = Field(..., description="URL pública para extrair o conteúdo.")
    filename: str = Field("knowledge", description="Nome base do arquivo salvo (sem extensão).")
