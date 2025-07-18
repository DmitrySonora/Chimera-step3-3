-- Схема базы данных Химера 2.0
-- Этап 3.1: Базовые таблицы с заделами на будущее

-- Таблица событий (заготовка под Event Sourcing)
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    user_id BIGINT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    data JSONB NOT NULL DEFAULT '{}',
    stream_id VARCHAR(255) NOT NULL DEFAULT '',  -- Заготовка для Event Sourcing
    version INTEGER DEFAULT 1,                   -- Заготовка для версионирования
    metadata JSONB DEFAULT '{}'                  -- Заготовка для метаданных
);

-- Таблица STM буфера (кратковременная память)
CREATE TABLE IF NOT EXISTS stm_buffer (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    emotion VARCHAR(50),              -- Заготовка для PerceptionActor (этап 4)
    mode VARCHAR(20),                 -- Заготовка для системы ролей (этап 5)
    importance_score INTEGER,         -- Заготовка для LTM (этап 7)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Критически важные индексы для производительности
CREATE INDEX IF NOT EXISTS idx_events_user_id_timestamp 
    ON events(user_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_events_type_timestamp 
    ON events(event_type, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_stm_buffer_user_created 
    ON stm_buffer(user_id, created_at DESC);

-- JSONB индексы для будущих этапов
CREATE INDEX IF NOT EXISTS idx_events_data_gin 
    ON events USING GIN (data);

-- Комментарии к таблицам
COMMENT ON TABLE events IS 'История всех событий системы (Event Sourcing ready)';
COMMENT ON TABLE stm_buffer IS 'Кратковременная память пользователей (STM)';

COMMENT ON COLUMN events.stream_id IS 'ID потока событий для Event Sourcing (этап 7)';
COMMENT ON COLUMN events.version IS 'Версия события для concurrency control';
COMMENT ON COLUMN stm_buffer.emotion IS 'Эмоциональное состояние (для PerceptionActor, этап 4)';
COMMENT ON COLUMN stm_buffer.mode IS 'Режим работы системы (для ролей, этап 5)';
COMMENT ON COLUMN stm_buffer.importance_score IS 'Важность для долговременной памяти (этап 7)';