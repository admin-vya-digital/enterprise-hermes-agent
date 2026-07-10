from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from docker_api.clients.vya_client import VyaClient, VyaApiError, get_vya_client
from docker_api.models.knowledge import KnowledgeUrlRequest

router = APIRouter(prefix="/agents/{agent_id}/knowledge", tags=["knowledge"])


def _raise_upstream(exc: VyaApiError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("")
async def list_knowledge(agent_id: str, client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.list_knowledge(agent_id)
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.post("")
async def add_knowledge_url(agent_id: str, body: KnowledgeUrlRequest, client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.add_knowledge_url(agent_id, body.model_dump())
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.post("/upload")
async def upload_knowledge(
    agent_id: str,
    client: VyaClient = Depends(get_vya_client),
    file: UploadFile = File(...),
):
    try:
        content = await file.read()
        return await client.upload_knowledge(agent_id, file.filename or "document", content)
    except VyaApiError as exc:
        _raise_upstream(exc)
