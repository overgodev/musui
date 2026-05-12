from datetime import datetime, timezone

from fastapi import FastAPI

from services.llm_response.app.service import ResponseGenerator
from services.moderation.app.service import ModerationService
from services.orchestrator.app.decision import DecisionEngine
from services.persona.app.service import PersonaEngine
from shared.ai_streamer.config import CommonSettings
from shared.ai_streamer.logging import configure_logging
from shared.ai_streamer.models import (
    ChatMessage,
    PersonaState,
    ReplyDecision,
    ReplyRequest,
    StreamContext,
)

settings = CommonSettings(service_name="orchestrator")
configure_logging(settings.service_name, settings.log_level)

app = FastAPI(title="orchestrator", version="0.1.0")
decision_engine = DecisionEngine(settings.reply_cooldown_seconds)
moderation_service = ModerationService(settings.moderation_rules_path)
persona_engine = PersonaEngine(settings.persona_path)
response_generator = ResponseGenerator()

_last_reply_at: datetime | None = None
_recent_replied_author_ids: list[str] = []
_recent_bot_replies: list[str] = []


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "orchestrator"}


@app.post("/decide", response_model=ReplyDecision)
async def decide(message: ChatMessage) -> ReplyDecision:
    global _last_reply_at

    moderation = moderation_service.classify(message.text)
    if not decision_engine.select_reply_candidate(
        message=message,
        moderation=moderation,
        recent_replied_author_ids=_recent_replied_author_ids[-10:],
        recent_bot_replies=_recent_bot_replies[-10:],
        last_reply_at=_last_reply_at,
    ):
        return decision_engine.build_skip_decision("cooldown_or_low_priority")

    persona_state = PersonaState(current_topic="live-chat", current_game="demo-build")
    context = StreamContext(current_topic="live-chat", current_game="demo-build")
    artifacts = persona_engine.build_prompt_artifacts(context, persona_state)
    reply_request = ReplyRequest(
        recent_messages=[message],
        target_message=message,
        persona_state=persona_state,
        memory_summary="running joke: blame the ping when the game glitches",
        safety=moderation,
    )
    decision = response_generator.generate(
        reply_request,
        artifacts.system_prompt,
        artifacts.style_constraints,
    )
    if decision.should_reply and decision.reply_text_th:
        _last_reply_at = datetime.now(timezone.utc)
        _recent_replied_author_ids.append(message.author.author_id)
        _recent_bot_replies.append(moderation.normalized_text)
    return decision
