from typing import Optional

from pydantic import BaseModel, Field


class CalendarEventRequest(BaseModel):
    summary: str
    start: str = Field(..., description="ISO 8601 com timezone.")
    end: str = Field(..., description="ISO 8601 com timezone.")
    location: str = ""
    description: str = ""
    attendees: str = Field("", description="E-mails separados por vírgula.")
    calendar: str = "primary"


class GoogleOAuthClientDetails(BaseModel):
    client_id: str
    project_id: str
    auth_uri: str = "https://accounts.google.com/o/oauth2/auth"
    token_uri: str = "https://oauth2.googleapis.com/token"
    auth_provider_x509_cert_url: str = "https://www.googleapis.com/oauth2/v1/certs"
    client_secret: str
    redirect_uris: list[str] = Field(default_factory=lambda: ["http://localhost"])


class CalendarClientSecretRequest(BaseModel):
    installed: Optional[GoogleOAuthClientDetails] = None
    web: Optional[GoogleOAuthClientDetails] = None


class CalendarAuthCodeRequest(BaseModel):
    code: str = Field(..., description="Código OAuth ou URL de callback completa.")
