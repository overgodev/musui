from pydantic_settings import BaseSettings, SettingsConfigDict


class CommonSettings(BaseSettings):
    service_name: str = "unknown"
    service_port: int = 8000
    environment: str = "dev"
    log_level: str = "INFO"
    redis_url: str = "redis://redis:6379/0"
    postgres_dsn: str = "postgresql+psycopg://streamer:streamer@postgres:5432/streamer"
    openai_api_key: str | None = None
    youtube_api_key: str | None = None
    youtube_live_chat_id: str | None = None
    youtube_channel_id: str | None = None
    youtube_mode: str = "mock"
    persona_path: str = "infra/personas/namwa.yaml"
    moderation_rules_path: str = "infra/moderation/rules.yaml"
    tts_provider: str = "stub"
    tts_voice_id: str = "namwa-v1"
    reply_cooldown_seconds: int = 6
    obs_websocket_url: str = "ws://obs:4455"
    obs_websocket_password: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
