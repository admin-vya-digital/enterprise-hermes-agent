from pydantic import BaseModel, Field


class SkillsRequest(BaseModel):
    enable: list[str] = Field(default_factory=list, description="Toolsets a habilitar neste perfil.")
    disable: list[str] = Field(default_factory=list, description="Toolsets a desabilitar neste perfil.")
