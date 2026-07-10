from pydantic import BaseModel, Field

CONTACT_TYPES = ("owner", "cliente")


class ContactRequest(BaseModel):
    contact_type: str = Field(..., description=f"Um de {CONTACT_TYPES}.")
    name: str = ""
    notes: str = ""
