from fastapi import FastAPI

from shared.ai_streamer.config import CommonSettings
from shared.ai_streamer.logging import configure_logging
from shared.ai_streamer.models import EmotionTag, VisemeEvent

settings = CommonSettings(service_name="avatar_bridge")
configure_logging(settings.service_name, settings.log_level)

app = FastAPI(title="avatar_bridge", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "avatar_bridge"}


@app.post("/visemes")
async def build_visemes(payload: dict[str, str]) -> dict[str, list[VisemeEvent] | str]:
    emotion = payload.get("emotion", EmotionTag.calm.value)
    visemes = [
        VisemeEvent(timestamp_ms=0, viseme="A", intensity=0.6),
        VisemeEvent(timestamp_ms=180, viseme="E", intensity=0.4),
        VisemeEvent(timestamp_ms=360, viseme="O", intensity=0.7),
    ]
    return {"emotion": emotion, "visemes": visemes}
