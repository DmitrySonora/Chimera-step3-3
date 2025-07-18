import pytest
import asyncio
from datetime import datetime
from events.conversation_events import UserMessageEvent, BotResponseEvent, ActorCoordinationEvent
from events.event_store import EventStore
from database.connection import DatabaseConnection


@pytest.fixture
async def test_db():
    """Создаем тестовое подключение к БД"""
    db = DatabaseConnection()
    await db.initialize()
    yield db
    await db.close()


@pytest.fixture
async def test_event_store(test_db):
    """Создаем тестовый Event Store"""
    store = EventStore(test_db)
    await store.initialize()
    yield store
    await store.shutdown()


@pytest.mark.asyncio
async def test_event_store_save_and_retrieve(test_event_store):
    """Тест сохранения и извлечения событий"""
    # Создаем тестовые события
    user_event = UserMessageEvent(
        user_id=99999,
        text="Тестовое сообщение",
        emotion="neutral"
    )
    
    bot_event = BotResponseEvent(
        user_id=99999,
        response_text="Тестовый ответ",
        generation_time_ms=100
    )
    
    # Сохраняем события
    assert await test_event_store.save_event(user_event) == True
    assert await test_event_store.save_event(bot_event) == True
    
    # Форсируем flush буфера
    await test_event_store._flush_buffer()
    
    # Извлекаем события
    events = await test_event_store.get_user_events(
        user_id=99999,
        event_types=["user_message", "bot_response"]
    )
    
    assert len(events) >= 2
    
    # Проверяем содержимое
    event_types = [e["event_type"] for e in events]
    assert "user_message" in event_types
    assert "bot_response" in event_types
    
    # Очистка тестовых данных
    async with test_event_store.db.acquire() as conn:
        await conn.execute("DELETE FROM events WHERE user_id = 99999")


@pytest.mark.asyncio
async def test_event_flow_coordination(test_event_store):
    """Тест событий координации между акторами"""
    # Создаем событие координации
    coord_event = ActorCoordinationEvent(
        source_actor="user_session",
        target_actor="memory",
        coordination_type="request",
        user_id=99999
    )
    
    # Сохраняем
    await test_event_store.save_event(coord_event)
    
    # Обновляем событие как успешное
    coord_event.coordination_type = "response"
    coord_event.duration_ms = 50
    coord_event.success = True
    
    await test_event_store.save_event(coord_event)
    
    # Форсируем flush
    await test_event_store._flush_buffer()
    
    # Получаем события по stream_id
    events = await test_event_store.get_events_by_stream(
        stream_id=coord_event.stream_id
    )
    
    assert len(events) >= 2
    
    # Очистка
    async with test_event_store.db.acquire() as conn:
        await conn.execute(f"DELETE FROM events WHERE stream_id = '{coord_event.stream_id}'")


@pytest.mark.asyncio
async def test_event_validation():
    """Тест валидации событий"""
    # Тест с слишком длинным текстом
    from config.events import EVENT_CONFIG
    max_length = EVENT_CONFIG["event_types"]["user_message"]["max_text_length"]
    
    with pytest.raises(ValueError) as exc_info:
        event = UserMessageEvent(
            user_id=12345,
            text="x" * (max_length + 1)
        )
    assert "Text length" in str(exc_info.value)
    
    # Тест с большими метаданными
    from events.base_event import BaseEvent
    large_metadata = {"data": "x" * 2000}
    
    with pytest.raises(ValueError) as exc_info:
        event = BaseEvent(
            event_type="test",
            user_id=12345,
            data={},
            metadata=large_metadata
        )
    assert "Metadata size" in str(exc_info.value)


@pytest.mark.asyncio
async def test_event_ordering(test_event_store):
    """Тест правильного порядка событий"""
    user_id = 88888
    
    # Создаем серию событий с задержками
    for i in range(5):
        event = UserMessageEvent(
            user_id=user_id,
            text=f"Сообщение {i}"
        )
        await test_event_store.save_event(event)
        await asyncio.sleep(0.1)  # Небольшая задержка
    
    # Форсируем flush
    await test_event_store._flush_buffer()
    
    # Получаем события
    events = await test_event_store.get_user_events(
        user_id=user_id,
        event_types=["user_message"],
        limit=10
    )
    
    # Проверяем, что они в правильном порядке (DESC)
    assert len(events) == 5
    for i in range(1, len(events)):
        # Каждое следующее событие должно быть старше предыдущего
        assert events[i]["timestamp"] < events[i-1]["timestamp"]
    
    # Очистка
    async with test_event_store.db.acquire() as conn:
        await conn.execute(f"DELETE FROM events WHERE user_id = {user_id}")