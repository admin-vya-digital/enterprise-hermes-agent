from fastapi import APIRouter, Depends, HTTPException

from docker_api.clients.vya_client import VyaClient, VyaApiError, get_vya_client
from docker_api.models.skills import SkillsRequest

router = APIRouter(prefix="/agents/{agent_id}/skills", tags=["skills"])


def _raise_upstream(exc: VyaApiError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("")
async def get_skills(agent_id: str, client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.get_skills(agent_id)
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.post("")
async def update_skills(agent_id: str, body: SkillsRequest, client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.set_skills(agent_id, body.model_dump())
    except VyaApiError as exc:
        _raise_upstream(exc)
