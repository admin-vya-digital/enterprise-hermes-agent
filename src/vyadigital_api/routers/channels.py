from fastapi import APIRouter, Depends, HTTPException, Response

from docker_api.clients.vya_client import VyaClient, VyaApiError, get_vya_client

router = APIRouter(prefix="/agents/{agent_id}/channels/whatsapp", tags=["channels"])


def _raise_upstream(exc: VyaApiError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("")
async def whatsapp_status(agent_id: str, client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.whatsapp_status(agent_id)
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.post("")
async def whatsapp_connect(agent_id: str, client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.whatsapp_connect(agent_id)
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.get("/qr")
async def whatsapp_qr(agent_id: str, client: VyaClient = Depends(get_vya_client)):
    try:
        content, content_type = await client.whatsapp_qr(agent_id)
    except VyaApiError as exc:
        _raise_upstream(exc)
        return
    return Response(content=content, media_type=content_type)


@router.delete("")
async def whatsapp_disconnect(
    agent_id: str, forget: bool = False, client: VyaClient = Depends(get_vya_client)
):
    try:
        return await client.whatsapp_disconnect(agent_id, forget=forget)
    except VyaApiError as exc:
        _raise_upstream(exc)
