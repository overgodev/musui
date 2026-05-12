from fastapi import FastAPI

from services.llm_response.app.service import ResponseGenerator
from services.persona.app.service import PersonaEngine
from shared.ai_streamer.config import CommonSettings
from shared.ai_streamer.logging import configure_logging
from shared.ai_streamer.models import ReplyDecision, ReplyRequest, StreamContext

settings = CommonSettings(service_name="llm_response")
configure_logging(settings.service_name, settings.log_level)
generator = ResponseGenerator()
persona_engine = PersonaEngine(settings.persona_path)

app = FastAPI(title="llm_response", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "llm_response"}


@app.post("/generate", response_model=ReplyDecision)
async def generate_reply(request: ReplyRequest) -> ReplyDecision:
    context = StreamContext(
        current_game=request.persona_state.current_game,
        current_topic=request.persona_state.current_topic,
        chat_speed=request.persona_state.chat_speed,
    )
    artifacts = persona_engine.build_prompt_artifacts(context, request.persona_state)
    return generator.generate(request, artifacts.system_prompt, artifacts.style_constraints)
