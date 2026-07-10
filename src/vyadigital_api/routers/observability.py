from fastapi import APIRouter, Depends, HTTPException

from docker_api.clients.vya_client import VyaClient, VyaApiError, get_vya_client

router = APIRouter(prefix="/agents/{agent_id}", tags=["observability"])


def _raise_upstream(exc: VyaApiError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/logs")
async def get_logs(
    agent_id: str,
    source: str = "gateway",
    lines: int = 100,
    client: VyaClient = Depends(get_vya_client),
):
    try:
        return await client.get_logs(agent_id, source=source, lines=lines)
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.get("/runs")
async def get_runs(agent_id: str, limit: int = 50, client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.get_runs(agent_id, limit=limit)
    except VyaApiError as exc:
        _raise_upstream(exc)
