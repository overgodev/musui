from fastapi import FastAPI

from shared.ai_streamer.config import CommonSettings
from shared.ai_streamer.logging import configure_logging
from shared.ai_streamer.models import SceneCommand

settings = CommonSettings(service_name="obs_bridge")
configure_logging(settings.service_name, settings.log_level)

app = FastAPI(title="obs_bridge", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "obs_bridge"}


@app.post("/scene", response_model=SceneCommand)
async def set_scene(command: SceneCommand) -> SceneCommand:
    return command
