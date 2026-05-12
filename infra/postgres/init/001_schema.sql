CREATE TABLE IF NOT EXISTS stream_sessions (
    id UUID PRIMARY KEY,
    platform VARCHAR(32) NOT NULL,
    title TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY,
    stream_session_id UUID REFERENCES stream_sessions(id),
    source_message_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    author_name TEXT NOT NULL,
    text_raw TEXT NOT NULL,
    text_normalized TEXT,
    source VARCHAR(32) NOT NULL DEFAULT 'youtube',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS moderation_results (
    id UUID PRIMARY KEY,
    chat_message_id UUID REFERENCES chat_messages(id),
    labels JSONB NOT NULL,
    severity INTEGER NOT NULL,
    action VARCHAR(32) NOT NULL,
    notes JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bot_replies (
    id UUID PRIMARY KEY,
    chat_message_id UUID REFERENCES chat_messages(id),
    reply_text_th TEXT,
    reply_text_en TEXT,
    should_reply BOOLEAN NOT NULL,
    emotion_tag VARCHAR(32),
    confidence_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    refusal_reason TEXT,
    internal_summary TEXT,
    audio_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS viewer_memory (
    id UUID PRIMARY KEY,
    viewer_id TEXT NOT NULL,
    viewer_name TEXT NOT NULL,
    memory_key TEXT NOT NULL,
    memory_value TEXT NOT NULL,
    importance INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS event_logs (
    id UUID PRIMARY KEY,
    trace_id TEXT NOT NULL,
    service_name VARCHAR(64) NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_author_id ON chat_messages(author_id);
CREATE INDEX IF NOT EXISTS idx_event_logs_trace_id ON event_logs(trace_id);
