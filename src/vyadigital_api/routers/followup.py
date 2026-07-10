from fastapi import APIRouter, Depends, HTTPException

from docker_api.clients.vya_client import VyaClient, VyaApiError, get_vya_client
from docker_api.models.followup import FollowupRequest

router = APIRouter(prefix="/agents/{agent_id}/followup", tags=["followup"])


def _raise_upstream(exc: VyaApiError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("")
async def list_followups(agent_id: str, client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.list_followups(agent_id)
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.post("", status_code=201)
async def create_followup(agent_id: str, body: FollowupRequest, client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.create_followup(agent_id, body.model_dump(exclude_none=True))
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.delete("/{job_id}", status_code=204)
async def delete_followup(agent_id: str, job_id: str, client: VyaClient = Depends(get_vya_client)):
    try:
        await client.delete_followup(agent_id, job_id)
    except VyaApiError as exc:
        _raise_upstream(exc)
