from fastapi import FastAPI

from docker_api.clients.vya_client import get_vya_client
from docker_api.core.config import get_settings
from docker_api.routers import agents, health

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(agents.router, prefix=settings.api_prefix)


@app.on_event("shutdown")
async def shutdown() -> None:
    await get_vya_client().aclose()
