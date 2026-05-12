from fastapi import FastAPI

from services.gateway.app.routers.health import router as health_router
from shared.ai_streamer.config import CommonSettings
from shared.ai_streamer.logging import configure_logging

settings = CommonSettings(service_name="gateway")
configure_logging(settings.service_name, settings.log_level)

app = FastAPI(title="gateway", version="0.1.0")
app.include_router(health_router)


@app.get("/services")
async def list_services() -> dict[str, list[dict[str, str]]]:
    return {
        "services": [
            {"name": "youtube", "url": "http://youtube:8001"},
            {"name": "orchestrator", "url": "http://orchestrator:8002"},
            {"name": "moderation", "url": "http://moderation:8003"},
            {"name": "persona", "url": "http://persona:8004"},
            {"name": "llm_response", "url": "http://llm-response:8005"},
            {"name": "tts", "url": "http://tts:8006"},
            {"name": "avatar_bridge", "url": "http://avatar-bridge:8007"},
            {"name": "obs_bridge", "url": "http://obs-bridge:8008"},
            {"name": "data_logging", "url": "http://data-logging:8009"},
        ]
    }
