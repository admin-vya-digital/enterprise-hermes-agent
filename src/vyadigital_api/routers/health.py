from fastapi import APIRouter, Depends

from docker_api.clients.vya_client import VyaClient, VyaApiError, get_vya_client
from docker_api.core.config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "app_name": settings.app_name, "environment": settings.environment}


@router.get("/health/upstream")
async def upstream_health(client: VyaClient = Depends(get_vya_client)) -> dict:
    try:
        upstream = await client.health()
    except VyaApiError as exc:
        return {"status": "error", "upstream_status_code": exc.status_code, "detail": exc.detail}
    return {"status": "ok", "upstream": upstream}
