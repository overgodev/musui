# Thai AI Streamer MVP Architecture

## Goal

Build a modular, production-minded MVP that can:

- read YouTube live chat in near real time
- decide whether to respond
- generate safe Thai replies in-character
- synthesize Thai speech
- emit avatar and OBS control events
- log everything for offline evaluation and later fine-tuning

## Assumptions

- V1 is API-first and rules-first.
- No base model training happens in V1.
- YouTube ingestion defaults to `mock` mode locally.
- TTS and LLM providers are adapter-based and can be replaced later.
- Thai is the primary response language, English is secondary.

## High-Level Services

- `gateway`: thin entrypoint for health, status, and future websocket aggregation.
- `youtube`: ingests chat via polling or streaming mode and normalizes events.
- `orchestrator`: picks messages, applies cooldowns, coordinates moderation/persona/generation/speech.
- `moderation`: Thai-first normalization and rules engine with extension hooks for model classifiers.
- `persona`: loads persona YAML and builds system prompt plus style constraints.
- `llm_response`: converts persona + memory + target message into a short stream-ready reply.
- `tts`: turns Thai text into audio metadata and output file paths.
- `avatar_bridge`: converts reply/emotion into viseme and expression events.
- `obs_bridge`: handles scenes, subtitles, and playback commands.
- `data_logging`: stores messages, moderation results, replies, latencies, and evaluation traces.

## Repo Tree

```text
docs/
  architecture.md
  local-development.md
infra/
  docker/
    python-service.Dockerfile
  moderation/
    rules.yaml
  personas/
    namwa.yaml
  postgres/
    init/
      001_schema.sql
scripts/
  replay_chat.py
services/
  gateway/
  youtube/
  orchestrator/
  moderation/
  persona/
  llm_response/
  tts/
  avatar_bridge/
  obs_bridge/
  data_logging/
shared/
  ai_streamer/
tests/
  fixtures/
```

## Request / Event Flow

1. `youtube` ingests a chat message from YouTube API or local mock mode.
2. The message is normalized into a `ChatMessage`.
3. `youtube` publishes the event to Redis stream `streamer.chat.events`.
4. `orchestrator` consumes the event and asks `moderation` for labels.
5. If the message is eligible, `orchestrator` loads prompt artifacts from `persona`.
6. `llm_response` generates a short Thai reply or declines.
7. `tts` synthesizes speech metadata.
8. `avatar_bridge` emits viseme and emotion events.
9. `obs_bridge` can play audio, switch scenes, and show subtitles.
10. `data_logging` records the full chain for later replay and evaluation.

## Redis Event Model

- Stream: `streamer.chat.events`
- Stream: `streamer.reply.events`
- Stream: `streamer.avatar.events`
- Pub/Sub fallback: `streamer.obs.commands`

Event payload shape:

```json
{
  "event_type": "chat.message.received",
  "trace_id": "uuid",
  "payload": {
    "message_id": "yt-123",
    "author": {"author_id": "u1", "display_name": "ปลาเผา"},
    "text": "วันนี้เล่นเกมอะไร",
    "source": "youtube"
  }
}
```

## PostgreSQL Schema Summary

- `stream_sessions`: one row per stream
- `chat_messages`: normalized inbound chat
- `moderation_results`: labels and actions for each message
- `bot_replies`: chosen replies, confidence, emotion, refusal reason
- `event_logs`: structured service-level telemetry
- `viewer_memory`: long-term facts keyed by viewer

See [001_schema.sql](../infra/postgres/init/001_schema.sql) for the concrete DDL.

## V1 Acceptance Criteria

- Local services start through Docker Compose.
- Mock YouTube events can be posted and normalized.
- Moderation labels Thai bait / spam / doxxing patterns.
- Orchestrator applies cooldown and prioritization logic.
- Persona engine builds prompt text from YAML.
- Response generator returns short Thai replies or declines safely.
- TTS / avatar / OBS bridges return structured stub outputs.
- Replay script can evaluate historical logs offline.
