from fastapi import APIRouter, Depends, HTTPException

from docker_api.clients.vya_client import VyaClient, VyaApiError, get_vya_client
from docker_api.models.agent import CreateAgentRequest, UpdateAgentRequest

router = APIRouter(prefix="/agents", tags=["agents"])


def _raise_upstream(exc: VyaApiError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("")
async def list_agents(client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.list_agents()
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.get("/{agent_id}")
async def get_agent(agent_id: str, client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.get_agent(agent_id)
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.post("", status_code=201)
async def create_agent(body: CreateAgentRequest, client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.create_agent(body.model_dump())
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.put("/{agent_id}")
async def update_agent(agent_id: str, body: UpdateAgentRequest, client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.update_agent(agent_id, body.model_dump(exclude_none=True))
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, client: VyaClient = Depends(get_vya_client)):
    try:
        await client.delete_agent(agent_id)
    except VyaApiError as exc:
        _raise_upstream(exc)
