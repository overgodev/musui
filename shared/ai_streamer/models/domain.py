from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field



def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Action(str, Enum):
    allow = "allow"
    ignore = "ignore"
    soft_refuse = "soft-refuse"
    hard_refuse = "hard-refuse"
    escalate = "escalate"


class ModerationLabel(str, Enum):
    safe = "safe"
    spam = "spam"
    sexual = "sexual"
    harassment = "harassment"
    hate = "hate"
    self_harm = "self-harm"
    illegal = "illegal"
    doxxing = "doxxing"
    impersonation_bait = "impersonation-bait"
    parasocial_bait = "parasocial-bait"


class MoodState(str, Enum):
    calm = "calm"
    excited = "excited"
    teasing = "teasing"
    focused = "focused"
    chaotic = "chaotic"


class EmotionTag(str, Enum):
    calm = "calm"
    excited = "excited"
    teasing = "teasing"
    focused = "focused"
    deadpan = "deadpan"


class ChatAuthor(BaseModel):
    author_id: str
    display_name: str
    badges: list[str] = Field(default_factory=list)
    is_moderator: bool = False
    is_member: bool = False
    is_owner: bool = False


class ChatMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    author: ChatAuthor
    text: str
    source: str = "youtube"
    language: str = "th"
    sent_at: datetime = Field(default_factory=utc_now)
    superchat_amount_micros: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StreamContext(BaseModel):
    stream_id: str = "local-dev-stream"
    current_game: str | None = None
    current_topic: str | None = None
    chat_speed: str = "normal"
    viewer_count: int = 0


class ModerationRequest(BaseModel):
    message: ChatMessage


class ModerationResult(BaseModel):
    normalized_text: str
    labels: list[ModerationLabel]
    severity: int
    action: Action
    notes: list[str] = Field(default_factory=list)


class PersonaState(BaseModel):
    name: str = "น้องน้ำหวาน"
    mood: MoodState = MoodState.calm
    energy: int = 60
    frustration: int = 5
    confidence: int = 70
    current_game: str | None = None
    current_topic: str | None = None
    chat_speed: str = "normal"


class PersonaPromptRequest(BaseModel):
    persona_path: str | None = None
    context: StreamContext
    state: PersonaState


class PersonaPromptArtifacts(BaseModel):
    system_prompt: str
    style_constraints: dict[str, Any]


class ReplyRequest(BaseModel):
    recent_messages: list[ChatMessage]
    target_message: ChatMessage
    persona_state: PersonaState
    memory_summary: str = ""
    safety: ModerationResult


class ReplyDecision(BaseModel):
    should_reply: bool
    reply_text_th: str | None = None
    reply_text_en: str | None = None
    emotion_tag: EmotionTag = EmotionTag.calm
    confidence_score: float = 0.0
    refusal_reason: str | None = None
    internal_summary: str | None = None


class TTSRequest(BaseModel):
    text: str
    voice_id: str
    language: str = "th"
    emotion: EmotionTag = EmotionTag.calm


class TTSResponse(BaseModel):
    audio_path: str
    duration_ms: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisemeEvent(BaseModel):
    timestamp_ms: int
    viseme: str
    intensity: float


class SceneCommand(BaseModel):
    scene_name: str
    reason: str
    subtitles: str | None = None


class LogEvent(BaseModel):
    event_type: str
    service_name: str
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
