from typing import Optional

from pydantic import BaseModel, Field


class CreateAgentRequest(BaseModel):
    agent_id: str = Field(..., description="Identificador único do agente (pasta em profiles/<agent_id>/).")
    name: str = Field(..., description="Nome de exibição do agente.")
    description: str = ""
    objective: str = ""
    personality: str = ""
    language: str = "pt-BR"
    model: str = ""
    temperature: Optional[float] = None
    initial_prompt: str = ""
    provider: str = Field(..., description="Provedor de LLM (ex: anthropic, openai, ollama).")
    provider_api_key: str = Field(..., description="Chave de API do provedor LLM escolhido.")
    whatsapp_mode: str = "bot"
    whatsapp_owner_number: str = ""


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    objective: Optional[str] = None
    personality: Optional[str] = None
    language: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    initial_prompt: Optional[str] = None
