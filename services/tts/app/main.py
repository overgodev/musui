from pathlib import Path

from fastapi import FastAPI

from shared.ai_streamer.config import CommonSettings
from shared.ai_streamer.logging import configure_logging
from shared.ai_streamer.models import TTSRequest, TTSResponse

settings = CommonSettings(service_name="tts")
configure_logging(settings.service_name, settings.log_level)

app = FastAPI(title="tts", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "tts", "provider": settings.tts_provider}


@app.post("/synthesize", response_model=TTSResponse)
async def synthesize(request: TTSRequest) -> TTSResponse:
    safe_name = request.voice_id.replace("/", "_")
    audio_path = Path("artifacts") / "audio" / f"{safe_name}.wav"
    return TTSResponse(
        audio_path=str(audio_path),
        duration_ms=max(900, len(request.text) * 85),
        metadata={
            "provider": settings.tts_provider,
            "voice_id": request.voice_id,
            "emotion": request.emotion.value,
        },
    )
