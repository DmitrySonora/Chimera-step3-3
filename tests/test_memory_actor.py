import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from actors.memory_actor import MemoryActor
from actors.message_types import create_memory_message


@pytest.fixture
async def mock_db():
    db = AsyncMock()
    conn = AsyncMock()

    class AcquireCM:
        async def __aenter__(self):
            return conn
        async def __aexit__(self, *args):
            pass

    db.acquire = lambda: AcquireCM()

    return db, conn


@pytest.mark.asyncio
async def test_memory_actor_initialization(mock_db):
    """Тест инициализации MemoryActor"""
    db, _ = mock_db
    
    actor = MemoryActor(db)
    assert actor.name == "memory"
    assert actor.stm_limit == 25  # Из конфига
    
    await actor.initialize()
    assert actor.is_initialized
    assert actor.is_running
    
    await actor.shutdown()


@pytest.mark.asyncio
async def test_store_user_message(mock_db):
    """Тест сохранения сообщения пользователя"""
    db, conn = mock_db
    conn.fetchval.return_value = 123  # ID сохраненного сообщения
    conn.fetchval.side_effect = [123, 10]  # ID и количество сообщений
    
    actor = MemoryActor(db)
    await actor.initialize()
    
    # Создаем сообщение
    message = create_memory_message(
        "store_user_message",
        {
            "user_id": 12345,
            "content": "Привет, Химера!",
            "emotion": "curious",
            "mode": "chat"
        }
    )
    
    # Обрабатываем
    result = await actor.handle_message(message)
    
    assert result["success"] is True
    assert result["message_id"] == 123
    assert "timestamp" in result
    
    # Проверяем вызов БД
    conn.fetchval.assert_called()
    
    await actor.shutdown()


@pytest.mark.asyncio
async def test_get_conversation_context(mock_db):
    """Тест получения контекста диалога"""
    db, conn = mock_db
    
    # Мокаем результат запроса
    mock_messages = [
        {
            'id': 1,
            'role': 'user',
            'content': 'Привет',
            'emotion': None,
            'mode': None,
            'created_at': datetime.utcnow()
        },
        {
            'id': 2,
            'role': 'assistant',
            'content': 'Здравствуй',
            'emotion': None,
            'mode': None,
            'created_at': datetime.utcnow()
        }
    ]
    conn.fetch.return_value = mock_messages
    
    actor = MemoryActor(db)
    await actor.initialize()
    
    # Запрашиваем контекст
    message = create_memory_message(
        "get_conversation_context",
        {"user_id": 12345, "limit": 10}
    )
    
    result = await actor.handle_message(message)
    
    assert result["success"] is True
    assert len(result["messages"]) == 2
    contents = [m["content"] for m in result["messages"]]
    assert "Привет" in contents
    assert "Здравствуй" in contents
    assert result["count"] == 2
    
    await actor.shutdown()


@pytest.mark.asyncio
async def test_cleanup_old_messages(mock_db):
    """Тест очистки старых сообщений"""
    db, conn = mock_db
    conn.fetchval.return_value = 30  # Количество сообщений
    
    actor = MemoryActor(db)
    await actor.initialize()
    
    # Запускаем очистку
    message = create_memory_message(
        "cleanup_old_messages",
        {"user_id": 12345}
    )
    
    result = await actor.handle_message(message)
    
    assert result["success"] is True
    assert result["deleted_count"] == 5  # 30 - 25 (лимит)
    assert result["remaining_count"] == 25
    
    # Проверяем вызов удаления
    conn.execute.assert_called()
    
    await actor.shutdown()


@pytest.mark.asyncio
async def test_message_type_validation():
    """Тест валидации типов сообщений"""
    from actors.message_types import create_memory_message
    
    # Успешное создание
    msg = create_memory_message(
        "store_user_message",
        {"user_id": 123, "content": "test"}
    )
    assert msg.type == "store_user_message"
    
    # Неизвестный тип
    with pytest.raises(ValueError):
        create_memory_message("unknown_type", {})
    
    # Отсутствующие поля
    with pytest.raises(ValueError):
        create_memory_message("store_user_message", {"content": "test"})  # Нет user_id


@pytest.mark.asyncio
async def test_performance_metrics(mock_db):
    """Тест сбора метрик производительности"""
    db, conn = mock_db
    conn.fetchval.return_value = 1
    
    actor = MemoryActor(db)
    await actor.initialize()
    
    # Выполняем несколько операций
    for i in range(5):
        message = create_memory_message(
            "store_user_message",
            {"user_id": 123, "content": f"Message {i}"}
        )
        await actor.handle_message(message)
    
    # Получаем метрики
    metrics = actor.get_performance_metrics()
    
    assert "store_latency_avg" in metrics
    assert "cleanup_operations" in metrics
    assert metrics["samples"]["store"] == 5
    
    await actor.shutdown()