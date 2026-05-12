from fastapi import FastAPI

from shared.ai_streamer.bus import RedisEventBus
from shared.ai_streamer.config import CommonSettings
from shared.ai_streamer.logging import configure_logging
from shared.ai_streamer.models import ChatMessage, LogEvent

settings = CommonSettings(service_name="youtube")
configure_logging(settings.service_name, settings.log_level)

app = FastAPI(title="youtube", version="0.1.0")
event_bus = RedisEventBus(settings.redis_url)
_mock_messages: list[ChatMessage] = []


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "youtube", "mode": settings.youtube_mode}


@app.get("/config")
async def config() -> dict[str, str | None]:
    return {
        "mode": settings.youtube_mode,
        "live_chat_id": settings.youtube_live_chat_id,
        "channel_id": settings.youtube_channel_id,
    }


@app.get("/messages")
async def list_messages() -> list[ChatMessage]:
    return _mock_messages[-50:]


@app.post("/ingest/mock", response_model=LogEvent)
async def ingest_mock(message: ChatMessage) -> LogEvent:
    _mock_messages.append(message)
    event = LogEvent(
        event_type="chat.message.received",
        service_name="youtube",
        payload=message.model_dump(mode="json"),
    )
    await event_bus.publish_stream("streamer.chat.events", event.model_dump(mode="json"))
    return event


@app.post("/reply")
async def send_reply(reply: dict[str, str]) -> dict[str, str]:
    return {
        "status": "queued",
        "message": reply.get("message", ""),
        "mode": settings.youtube_mode,
    }
