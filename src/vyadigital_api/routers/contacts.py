from fastapi import APIRouter, Depends, HTTPException

from docker_api.clients.vya_client import VyaClient, VyaApiError, get_vya_client
from docker_api.models.contact import ContactRequest

router = APIRouter(prefix="/agents/{agent_id}/contacts", tags=["contacts"])


def _raise_upstream(exc: VyaApiError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("")
async def list_contacts(agent_id: str, client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.list_contacts(agent_id)
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.get("/{phone}")
async def get_contact(agent_id: str, phone: str, client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.get_contact(agent_id, phone)
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.post("/{phone}")
async def upsert_contact(
    agent_id: str, phone: str, body: ContactRequest, client: VyaClient = Depends(get_vya_client)
):
    try:
        return await client.upsert_contact(agent_id, phone, body.model_dump())
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.delete("/{phone}", status_code=204)
async def delete_contact(agent_id: str, phone: str, client: VyaClient = Depends(get_vya_client)):
    try:
        await client.delete_contact(agent_id, phone)
    except VyaApiError as exc:
        _raise_upstream(exc)
