from fastapi import FastAPI

from shared.ai_streamer.config import CommonSettings
from shared.ai_streamer.logging import configure_logging
from shared.ai_streamer.models import LogEvent

settings = CommonSettings(service_name="data_logging")
configure_logging(settings.service_name, settings.log_level)

app = FastAPI(title="data_logging", version="0.1.0")
_events: list[LogEvent] = []


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "data_logging"}


@app.post("/events", response_model=LogEvent)
async def log_event(event: LogEvent) -> LogEvent:
    _events.append(event)
    return event


@app.get("/events")
async def list_events() -> list[LogEvent]:
    return _events[-100:]
