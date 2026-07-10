from fastapi import FastAPI

from docker_api.clients.vya_client import get_vya_client
from docker_api.core.config import get_settings
from docker_api.routers import agents, calendar, contacts, followup, health, knowledge, memory, skills

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(agents.router, prefix=settings.api_prefix)
app.include_router(skills.router, prefix=settings.api_prefix)
app.include_router(knowledge.router, prefix=settings.api_prefix)
app.include_router(calendar.router, prefix=settings.api_prefix)
app.include_router(followup.router, prefix=settings.api_prefix)
app.include_router(contacts.router, prefix=settings.api_prefix)
app.include_router(memory.router, prefix=settings.api_prefix)


@app.on_event("shutdown")
async def shutdown() -> None:
    await get_vya_client().aclose()
