from fastapi import FastAPI

from services.persona.app.service import PersonaEngine
from shared.ai_streamer.config import CommonSettings
from shared.ai_streamer.logging import configure_logging
from shared.ai_streamer.models import PersonaPromptArtifacts, PersonaPromptRequest

settings = CommonSettings(service_name="persona")
configure_logging(settings.service_name, settings.log_level)
engine = PersonaEngine(settings.persona_path)

app = FastAPI(title="persona", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "persona"}


@app.post("/prompt", response_model=PersonaPromptArtifacts)
async def build_prompt(request: PersonaPromptRequest) -> PersonaPromptArtifacts:
    return engine.build_prompt_artifacts(request.context, request.state)
