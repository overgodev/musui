import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from services.moderation.app.service import ModerationService
from services.orchestrator.app.decision import DecisionEngine
from shared.ai_streamer.models import ChatAuthor, ChatMessage


def replay(path: Path, rules_path: str, cooldown_seconds: int) -> dict[str, int]:
    moderation_service = ModerationService(rules_path)
    decision_engine = DecisionEngine(cooldown_seconds=cooldown_seconds)
    recent_authors: list[str] = []
    recent_bot_replies: list[str] = []
    last_reply_at = None
    stats = {"seen": 0, "replied": 0, "blocked": 0}

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            message = ChatMessage(
                message_id=row["message_id"],
                author=ChatAuthor(
                    author_id=row["author_id"],
                    display_name=row["author_name"],
                ),
                text=row["text"],
                sent_at=datetime.now(timezone.utc),
            )
            moderation = moderation_service.classify(message.text)
            stats["seen"] += 1
            if moderation.action.value != "allow":
                stats["blocked"] += 1
                continue
            should_reply = decision_engine.select_reply_candidate(
                message,
                moderation,
                recent_authors[-10:],
                recent_bot_replies[-10:],
                last_reply_at,
            )
            if should_reply:
                stats["replied"] += 1
                recent_authors.append(message.author.author_id)
                recent_bot_replies.append(moderation.normalized_text)
                last_reply_at = datetime.now(timezone.utc)

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay historical chat logs through MVP logic.")
    parser.add_argument("--input", required=True, type=Path, help="Path to JSONL chat log file.")
    parser.add_argument(
        "--rules-path",
        default="infra/moderation/rules.yaml",
        help="Moderation rules YAML path.",
    )
    parser.add_argument("--cooldown-seconds", default=6, type=int)
    args = parser.parse_args()

    stats = replay(args.input, args.rules_path, args.cooldown_seconds)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
