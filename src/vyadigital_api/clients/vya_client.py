from functools import lru_cache
from typing import Any

import httpx

from docker_api.core.config import get_settings


class VyaApiError(Exception):
    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"vya-workforce-api error {status_code}: {detail}")


class VyaClient:
    """Cliente HTTP para a vya-workforce-api (hermes-agent em homologação)."""

    def __init__(self, base_url: str, api_key: str, timeout: float):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.RequestError as exc:
            raise VyaApiError(503, f"vya-workforce-api unreachable: {exc}") from exc
        if response.status_code >= 400:
            raise VyaApiError(response.status_code, _safe_json(response))
        if response.status_code == 204 or not response.content:
            return None
        return _safe_json(response)

    async def health(self) -> Any:
        return await self._request("GET", "/health")

    async def list_agents(self) -> Any:
        return await self._request("GET", "/agents")

    async def get_agent(self, agent_id: str) -> Any:
        return await self._request("GET", f"/agents/{agent_id}")

    async def create_agent(self, payload: dict) -> Any:
        return await self._request("POST", "/agents", json=payload)

    async def update_agent(self, agent_id: str, payload: dict) -> Any:
        return await self._request("PUT", f"/agents/{agent_id}", json=payload)

    async def delete_agent(self, agent_id: str) -> None:
        await self._request("DELETE", f"/agents/{agent_id}")

    # ── skills ──────────────────────────────────────────────────────────────

    async def get_skills(self, agent_id: str) -> Any:
        return await self._request("GET", f"/agents/{agent_id}/skills")

    async def set_skills(self, agent_id: str, payload: dict) -> Any:
        return await self._request("POST", f"/agents/{agent_id}/skills", json=payload)

    # ── knowledge ───────────────────────────────────────────────────────────

    async def list_knowledge(self, agent_id: str) -> Any:
        return await self._request("GET", f"/agents/{agent_id}/knowledge")

    async def add_knowledge_url(self, agent_id: str, payload: dict) -> Any:
        return await self._request("POST", f"/agents/{agent_id}/knowledge", json=payload)

    async def upload_knowledge(self, agent_id: str, filename: str, content: bytes) -> Any:
        files = {"file": (filename, content)}
        return await self._request("POST", f"/agents/{agent_id}/knowledge/upload", files=files)

    # ── calendar ────────────────────────────────────────────────────────────

    async def calendar_status(self, agent_id: str) -> Any:
        return await self._request("GET", f"/agents/{agent_id}/calendar/connect")

    async def calendar_connect(self, agent_id: str, client_secret: dict) -> Any:
        return await self._request("POST", f"/agents/{agent_id}/calendar/connect", json=client_secret)

    async def calendar_auth_url(self, agent_id: str) -> Any:
        return await self._request("GET", f"/agents/{agent_id}/calendar/connect/auth-url")

    async def calendar_auth_code(self, agent_id: str, code: str) -> Any:
        return await self._request(
            "POST", f"/agents/{agent_id}/calendar/connect/auth-code", json={"code": code}
        )

    async def calendar_schedule(self, agent_id: str, payload: dict) -> Any:
        return await self._request("POST", f"/agents/{agent_id}/calendar/schedule", json=payload)

    # ── followup ────────────────────────────────────────────────────────────

    async def list_followups(self, agent_id: str) -> Any:
        return await self._request("GET", f"/agents/{agent_id}/followup")

    async def create_followup(self, agent_id: str, payload: dict) -> Any:
        return await self._request("POST", f"/agents/{agent_id}/followup", json=payload)

    async def delete_followup(self, agent_id: str, job_id: str) -> None:
        await self._request("DELETE", f"/agents/{agent_id}/followup/{job_id}")

    # ── contacts ────────────────────────────────────────────────────────────

    async def list_contacts(self, agent_id: str) -> Any:
        return await self._request("GET", f"/agents/{agent_id}/contacts")

    async def get_contact(self, agent_id: str, phone: str) -> Any:
        return await self._request("GET", f"/agents/{agent_id}/contacts/{phone}")

    async def upsert_contact(self, agent_id: str, phone: str, payload: dict) -> Any:
        return await self._request("POST", f"/agents/{agent_id}/contacts/{phone}", json=payload)

    async def delete_contact(self, agent_id: str, phone: str) -> None:
        await self._request("DELETE", f"/agents/{agent_id}/contacts/{phone}")

    # ── memory ──────────────────────────────────────────────────────────────

    async def get_memory(self, agent_id: str, contact_uid: str) -> Any:
        return await self._request("GET", f"/agents/{agent_id}/memory/{contact_uid}")

    async def write_memory(self, agent_id: str, contact_uid: str, payload: dict) -> Any:
        return await self._request("POST", f"/agents/{agent_id}/memory/{contact_uid}", json=payload)


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


@lru_cache
def get_vya_client() -> VyaClient:
    settings = get_settings()
    return VyaClient(
        base_url=settings.vya_api_base_url,
        api_key=settings.vya_api_key,
        timeout=settings.vya_api_timeout_seconds,
    )
