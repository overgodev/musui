# Local Development

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[test]
```

## Run Tests

```bash
pytest
```

## Run One Service

```bash
uvicorn services.orchestrator.app.main:app --reload --port 8002
```

## Run Full Stack

```bash
docker compose up --build
```

## Local Mock Flow

1. Start the stack.
2. `POST` a message to `youtube` mock ingest.
3. Inspect moderation and orchestration endpoints directly.
4. Use `scripts/replay_chat.py` for offline evaluation against historical logs.

## Config

Copy `.env.example` to `.env` and adjust:

- `OPENAI_API_KEY`
- `YOUTUBE_API_KEY`
- `YOUTUBE_LIVE_CHAT_ID`
- `OBS_WEBSOCKET_PASSWORD`
- `PERSONA_PATH`
- `MODERATION_RULES_PATH`

## Notes

- The shared package contains common domain models and settings.
- TTS and LLM services are stubs by default so the system can boot without external credentials.
- Legacy prototype scripts remain available in `speech to text/` and `tts/`.
