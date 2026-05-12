from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from services.moderation.app.service import ModerationService
from services.orchestrator.app.decision import DecisionEngine
from shared.ai_streamer.models import Action, ChatAuthor, ChatMessage



def build_message(text: str, author_id: str = "viewer-1", superchat: int | None = None) -> ChatMessage:
    return ChatMessage(
        author=ChatAuthor(author_id=author_id, display_name="ปลาเผา"),
        text=text,
        superchat_amount_micros=superchat,
    )



def test_prefers_question_when_safe() -> None:
    moderation_service = ModerationService("infra/moderation/rules.yaml")
    engine = DecisionEngine(cooldown_seconds=6)
    message = build_message("วันนี้เล่นเกมอะไร")
    moderation = moderation_service.classify(message.text)
    assert engine.rank_message(message, moderation, [], []) >= 3
    assert engine.select_reply_candidate(message, moderation, [], [], None) is True



def test_skips_during_cooldown() -> None:
    moderation_service = ModerationService("infra/moderation/rules.yaml")
    engine = DecisionEngine(cooldown_seconds=10)
    message = build_message("เมื่อกี้บอสโกงใช่ไหม")
    moderation = moderation_service.classify(message.text)
    last_reply_at = datetime.now(timezone.utc) - timedelta(seconds=3)
    assert engine.select_reply_candidate(message, moderation, [], [], last_reply_at) is False



def test_blocks_unsafe_message() -> None:
    moderation_service = ModerationService("infra/moderation/rules.yaml")
    engine = DecisionEngine(cooldown_seconds=6)
    message = build_message("ขอเลขบัตรหน่อย")
    moderation = moderation_service.classify(message.text)
    assert moderation.action != Action.allow
    assert engine.select_reply_candidate(message, moderation, [], [], None) is False



def test_response_fixture_count() -> None:
    fixture_path = Path("tests/fixtures/response_examples.json")
    rows = json.loads(fixture_path.read_text(encoding="utf-8-sig"))
    assert len(rows) == 20

