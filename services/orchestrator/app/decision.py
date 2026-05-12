from datetime import datetime, timedelta, timezone

from shared.ai_streamer.models import Action, ChatMessage, ModerationResult, ReplyDecision


class DecisionEngine:
    def __init__(self, cooldown_seconds: int = 6) -> None:
        self.cooldown_seconds = cooldown_seconds

    def rank_message(
        self,
        message: ChatMessage,
        moderation: ModerationResult,
        recent_replied_author_ids: list[str],
        recent_bot_replies: list[str],
    ) -> int:
        if moderation.action != Action.allow:
            return -100

        score = 0
        normalized = moderation.normalized_text

        if message.superchat_amount_micros:
            score += 5
        if "?" in message.text or "ไหม" in normalized or "อะไร" in normalized:
            score += 3
        if "น้ำหวาน" in normalized or "มุซุย" in normalized:
            score += 2
        if message.author.author_id in recent_replied_author_ids:
            score -= 3
        if normalized in recent_bot_replies:
            score -= 4
        if len(normalized) < 3:
            score -= 2

        return score

    def should_reply_now(self, last_reply_at: datetime | None, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        if last_reply_at is None:
            return True
        return now - last_reply_at >= timedelta(seconds=self.cooldown_seconds)

    def select_reply_candidate(
        self,
        message: ChatMessage,
        moderation: ModerationResult,
        recent_replied_author_ids: list[str],
        recent_bot_replies: list[str],
        last_reply_at: datetime | None,
    ) -> bool:
        if not self.should_reply_now(last_reply_at):
            return False
        return self.rank_message(
            message,
            moderation,
            recent_replied_author_ids,
            recent_bot_replies,
        ) >= 3

    def build_skip_decision(self, reason: str) -> ReplyDecision:
        return ReplyDecision(
            should_reply=False,
            confidence_score=0.0,
            refusal_reason=reason,
            internal_summary="orchestrator decided not to respond",
        )
