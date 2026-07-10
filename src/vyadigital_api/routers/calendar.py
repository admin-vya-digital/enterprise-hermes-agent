from fastapi import APIRouter, Depends, HTTPException

from docker_api.clients.vya_client import VyaClient, VyaApiError, get_vya_client
from docker_api.models.calendar import (
    CalendarAuthCodeRequest,
    CalendarClientSecretRequest,
    CalendarEventRequest,
)

router = APIRouter(prefix="/agents/{agent_id}/calendar", tags=["calendar"])


def _raise_upstream(exc: VyaApiError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/connect")
async def calendar_status(agent_id: str, client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.calendar_status(agent_id)
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.post("/connect")
async def calendar_connect(
    agent_id: str, body: CalendarClientSecretRequest, client: VyaClient = Depends(get_vya_client)
):
    try:
        return await client.calendar_connect(agent_id, body.model_dump(exclude_none=True))
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.get("/connect/auth-url")
async def calendar_auth_url(agent_id: str, client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.calendar_auth_url(agent_id)
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.post("/connect/auth-code")
async def calendar_auth_code(
    agent_id: str, body: CalendarAuthCodeRequest, client: VyaClient = Depends(get_vya_client)
):
    try:
        return await client.calendar_auth_code(agent_id, body.code)
    except VyaApiError as exc:
        _raise_upstream(exc)


@router.post("/schedule")
async def calendar_schedule(agent_id: str, body: CalendarEventRequest, client: VyaClient = Depends(get_vya_client)):
    try:
        return await client.calendar_schedule(agent_id, body.model_dump())
    except VyaApiError as exc:
        _raise_upstream(exc)
