---
tags:
  - musui
  - architecture
  - vtuber
  - thai-ai
  - moc
created: 2026-05-13
type: map
---

# musui — Thai AI VTuber Architecture Map

**musui** is a production-minded MVP for a Thai AI VTuber streamer — a modular FastAPI monorepo that reads YouTube live chat, generates safe Thai replies in-character, synthesizes speech with RVC voice models, and drives avatar + OBS output in real time.

---

## Project Root

| File | Purpose |
|------|---------|
| [[README]] | Project overview & quick start |
| [[docs/architecture]] | High-level design & acceptance criteria |
| [[docs/local-development]] | Dev environment setup |
| `docker-compose.yml` | Orchestrates all 11 services |
| `pyproject.toml` | Python package & dependency config |
| `.env.example` | Environment variable template |

> [!warning] V1 Scope
> V1 is API-first and rules-first. No base model training happens in V1. YouTube ingestion defaults to `mock` mode locally. TTS and LLM providers are adapter-based and can be swapped later.

---

## Service Pipeline

> [!info] Event Flow
> YouTube publishes `ChatMessage` events to Redis stream `streamer.chat.events`. Orchestrator consumes, fans out to Moderation + Persona, then drives LLM → TTS → Avatar/OBS → Data Logging. All services communicate via typed Pydantic models from [[Domain Models]].

```
YouTube :8001
    ↓  streamer.chat.events (Redis)
Orchestrator :8002
    ├──→ Moderation :8003  ──→┐
    └──→ Persona :8004    ──→ LLM Response :8005
                               ↓  TTSRequest
                           TTS :8006
                          ┌────┴────┐
              Avatar Bridge :8007  OBS Bridge :8008
                          └────┬────┘
                        Data Logging :8009
                               ↓
                         PostgreSQL :5432
```

1. **[[YouTube Service]] `:8001`** — Chat ingestion (mock / live), normalises raw messages into `ChatMessage` — `services/youtube/`
2. **[[Orchestrator]] `:8002`** — Decision engine, cooldown logic, coordinates all downstream services — `services/orchestrator/`
3. **[[Moderation]] `:8003`** — Thai-first rules engine, 10 label categories (spam, sexual, harassment, hate, doxxing, self-harm, illegal, impersonation-bait, parasocial-bait, safe) — `services/moderation/`
4. **[[Persona]] `:8004`** — Loads [[namwa|namwa.yaml]], builds system prompt + style constraints, tracks mood & energy state — `services/persona/`
5. **[[LLM Response]] `:8005`** — Generates short Thai replies using persona + memory + safety context — `services/llm_response/`
6. **[[TTS]] `:8006`** — Text-to-speech synthesis, RVC voice model adapter — `services/tts/`
7. **[[Avatar Bridge]] `:8007`** — Converts `EmotionTag` → viseme + expression events — `services/avatar_bridge/`
8. **[[OBS Bridge]] `:8008`** — Scene control, subtitles, audio playback commands — `services/obs_bridge/`
9. **[[Data Logging]] `:8009`** — Stores full chain (messages, moderation, replies, latencies) to PostgreSQL for offline replay/eval — `services/data_logging/`
10. **[[Gateway]] `:8000`** — Thin entrypoint: health, status, future WebSocket aggregation — `services/gateway/`

---

## Persona — น้องน้ำหวาน

> [!example] Namwa Persona
> Loaded from [[namwa|infra/personas/namwa.yaml]] — a playful, warm Thai streamer who is like a chat-room regular friend. Indie/story games. Witty teasing that never cuts deep.

| Property | Value |
|----------|-------|
| **Name** | น้องน้ำหวาน (Namwa) |
| **Tone** | ขี้เล่น ฉลาดไว ตอบสั้นคม |
| **Language** | Thai-first · English only when necessary |
| **Max sentences** | 3 |
| **Moods** | `calm` · `excited` · `teasing` · `focused` · `chaotic` |
| **Taboos** | Doxxing · real relationship promises · illegal advice · sexual content |
| **Recurring jokes** | Ping-blaming · server-lag muk · "team in head is smiling" |
| **Banned** | Claiming to be human · promising personal relationships |

---

## Infrastructure

- **[[Redis]] `:6379`**
  - Stream `streamer.chat.events` — inbound chat
  - Stream `streamer.reply.events` — generated replies
  - Stream `streamer.avatar.events` — avatar drive events
  - Pub/Sub `streamer.obs.commands` — OBS control

- **[[PostgreSQL]] `:5432`** — `infra/postgres/init/001_schema.sql`
  - `stream_sessions` — one row per stream
  - `chat_messages` — normalised inbound chat
  - `moderation_results` — labels & actions per message
  - `bot_replies` — chosen replies, confidence, emotion, refusal reason
  - `event_logs` — structured service-level telemetry
  - `viewer_memory` — long-term facts keyed by viewer

- **[[Docker Compose]]** — `docker-compose.yml` + `infra/docker/python-service.Dockerfile`
  - 11 services: 9 FastAPI microservices + Redis + PostgreSQL

> [!tip] Quick Start
> ```bash
> pip install -e .[test]
> pytest
> docker compose up --build
> ```

---

## Shared Library

`shared/ai_streamer/`

- **[[Domain Models]]** — `models/domain.py`
  All Pydantic models: `ChatMessage` · `ChatAuthor` · `ModerationRequest` · `ModerationResult` · `PersonaState` · `ReplyRequest` · `ReplyDecision` · `TTSRequest` · `TTSResponse` · `VisemeEvent` · `SceneCommand` · `LogEvent`

- **[[RedisEventBus]]** — `bus.py`
  `publish_stream()` (xadd) · `publish_channel()` (pub/sub)

- **[[Config & Logging]]** — `config.py` · `logging.py`
  Shared configuration · structured logging across all services

---

## Voice Models (RVC)

Stored in `voice model/` — used by TTS service and legacy scripts.

| Model | Files |
|-------|-------|
| **mosui ★** *(primary persona voice)* | `mosui.pth` · `mosui.index` |
| mosui v2 | `mosui_v2.pth` · `mosui_v2.index` |
| akane v2 | `akanev2.pth` · index |
| suisei (SuiseiFT) | `SuiseiFT.pth` · index |
| chaaym v1 | `chaaym_v1.pth` · index |
| FubukiUi | `FubukiUi.pth` · index |
| Amelia Watson | `G_30400.pth` · `D_30400.pth` · `config.json` |

Pipeline scripts: `scripts/tts_with_*_rvc310.py`
Replay script: `scripts/replay_chat.py`

---

## VApp (Electron)

- **[[VTube AI]]** — `VApp/` · `package.json` → `vtube-ai`
  Electron desktop app connecting **LM Studio** + **VTube Studio** + **TTS** via WebSocket / HTTP
  - `src/main.js` — main process
  - `src/preload.js` — IPC bridge
  - `renderer/index.html` + `renderer/app.js` — UI
  - Deps: `ws` · `axios` · `node-fetch` · `say`

---

## Legacy / Experimental

Preserved original experiments alongside the new architecture.

- **[[Speech to Text]]** — `speech to text/`
  Google STT · OpenAI Whisper · `audioutils.py` · combined pipeline

- **[[TTS Scripts]]** — `tts/` + `scripts/`
  `pyttsx3` · `edge-tts` · RVC310 pipeline per voice model

- **Audio Artifacts** — `artifacts/audio/*.wav`
  Output samples: `mosui_out.wav` · `akane_out.wav` · `chaaym_out.wav` · `suisei_out.wav`

---

## Tests

- **[[test_decision_engine]]** — `tests/test_decision_engine.py` — orchestrator decision & cooldown logic
- **[[test_moderation]]** — `tests/test_moderation.py` — moderation label & action rules
- **Fixtures** — `tests/fixtures/response_examples.json`

Run with: `pytest`
