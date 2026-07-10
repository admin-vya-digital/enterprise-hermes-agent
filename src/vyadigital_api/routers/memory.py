from fastapi import APIRouter, Depends, HTTPException

from docker_api.clients.vya_client import VyaClient, VyaApiError, get_vya_client
from docker_api.models.memory import WriteMemoryRequest

router = APIRouter(prefix="/agents/{agent_id}/memory", tags=["memory"])


def _raise_upstream(exc: VyaApiError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/{contact_uid}")
async def get_memory(agent_id: str, contact_uid: str, client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.get_memory(agent_id, contact_uid)
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.post("/{contact_uid}")
async def write_memory(
    agent_id: str, contact_uid: str, body: WriteMemoryRequest, client: VyaClient = Depends(get_vya_client)
):
    try:
        return await client.write_memory(agent_id, contact_uid, body.model_dump())
    except VyaApiError as exc:
        _raise_upstream(exc)
