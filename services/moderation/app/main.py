from fastapi import FastAPI

from services.moderation.app.service import ModerationService
from shared.ai_streamer.config import CommonSettings
from shared.ai_streamer.logging import configure_logging
from shared.ai_streamer.models import ModerationRequest, ModerationResult

settings = CommonSettings(service_name="moderation")
configure_logging(settings.service_name, settings.log_level)
service = ModerationService(settings.moderation_rules_path)

app = FastAPI(title="moderation", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "moderation"}


@app.post("/moderate", response_model=ModerationResult)
async def moderate(request: ModerationRequest) -> ModerationResult:
    return service.classify(request.message.text)
