"""
vya_api_client.py — cliente HTTP para o vyadigital_api (container
`hermes-interaction-api`, imagem adminvyadigital/hermes-api), usado só para
o que exige atravessar container (canal WhatsApp: status/connect/disconnect/QR).

Tudo que é leitura/escrita de arquivo dentro de profiles/<id>/ (conversas,
contatos, leads, produto, agenda, cron, logs) usa o volume compartilhado
diretamente em server.py — não passa por aqui. Ver ARCHITECTURE_NOTES.md.

Modelado no cliente equivalente já existente em
enterprise-hermes-agent/src/vyadigital_api/clients/vya_client.py — mas
falando com o vyadigital_api (que já fala com o vya-workforce-api), não
com o vya-workforce-api diretamente.
"""

import os
from typing import Any

import aiohttp

BASE_URL = os.environ.get("VYA_API_BASE_URL", "http://hermes-interaction-api:8000")
API_PREFIX = os.environ.get("VYA_API_PREFIX", "/api/v1")
API_KEY = os.environ.get("VYA_API_KEY", "")
TIMEOUT_SECONDS = float(os.environ.get("VYA_API_TIMEOUT_SECONDS", "30"))


class VyaApiError(Exception):
    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"vyadigital_api error {status_code}: {detail}")


def _headers() -> dict:
    return {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}


async def _request(method: str, path: str, **kwargs: Any) -> Any:
    url = f"{BASE_URL}{API_PREFIX}{path}"
    timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=_headers()) as sess:
            async with sess.request(method, url, **kwargs) as resp:
                if resp.status >= 400:
                    detail = await _safe_json(resp)
                    raise VyaApiError(resp.status, detail)
                if resp.status == 204 or resp.content_length == 0:
                    return None
                return await _safe_json(resp)
    except aiohttp.ClientError as e:
        raise VyaApiError(503, f"vyadigital_api indisponível: {e}") from e


async def _safe_json(resp: aiohttp.ClientResponse) -> Any:
    try:
        return await resp.json()
    except Exception:
        return await resp.text()


async def restart_agent(agent_id: str) -> Any:
    return await _request("POST", f"/agents/{agent_id}/restart")


async def whatsapp_status(agent_id: str) -> Any:
    return await _request("GET", f"/agents/{agent_id}/channels/whatsapp")


async def whatsapp_connect(agent_id: str) -> Any:
    return await _request("POST", f"/agents/{agent_id}/channels/whatsapp")


async def whatsapp_disconnect(agent_id: str, forget: bool = False) -> Any:
    return await _request(
        "DELETE", f"/agents/{agent_id}/channels/whatsapp", params={"forget": str(forget).lower()}
    )


async def whatsapp_qr(agent_id: str) -> tuple[bytes, str]:
    """QR vem como PNG binário — não passa pelo _request/_safe_json."""
    url = f"{BASE_URL}{API_PREFIX}/agents/{agent_id}/channels/whatsapp/qr"
    timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=_headers()) as sess:
            async with sess.get(url) as resp:
                if resp.status >= 400:
                    detail = await _safe_json(resp)
                    raise VyaApiError(resp.status, detail)
                content = await resp.read()
                return content, resp.headers.get("content-type", "image/png")
    except aiohttp.ClientError as e:
        raise VyaApiError(503, f"vyadigital_api indisponível: {e}") from e
