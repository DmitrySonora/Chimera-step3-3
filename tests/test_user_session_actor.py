import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from actors.user_session_actor import UserSessionActor
from actors.memory_actor import MemoryActor
from events.event_store import EventStore
from config.coordination import COORDINATION_CONFIG


@pytest.fixture
async def mock_components():
    """Создаем моки для компонентов"""
    # Mock MemoryActor
    memory_actor = AsyncMock(spec=MemoryActor)
    memory_actor.handle_message = AsyncMock()
    memory_actor.handle_message.return_value = {
        "success": True,
        "messages": [
            {"role": "user", "content": "Привет"},
            {"role": "assistant", "content": "Здравствуй"}
        ],
        "count": 2
    }
    
    # Mock EventStore
    event_store = AsyncMock(spec=EventStore)
    event_store.save_event = AsyncMock(return_value=True)
    
    # Mock DeepSeek service
    with patch('actors.user_session_actor.deepseek_service') as mock_deepseek:
        mock_deepseek.ask_deepseek = AsyncMock(return_value="Тестовый ответ Химеры")
        
        yield {
            "memory_actor": memory_actor,
            "event_store": event_store,
            "deepseek_service": mock_deepseek
        }


@pytest.mark.asyncio
async def test_user_session_actor_initialization(mock_components):
    """Тест инициализации UserSessionActor"""
    actor = UserSessionActor(
        memory_actor=mock_components["memory_actor"],
        event_store=mock_components["event_store"]
    )
    
    assert actor.name == "user_session"
    assert actor.memory_actor == mock_components["memory_actor"]
    assert actor.event_store == mock_components["event_store"]
    assert actor.actor_timeout == COORDINATION_CONFIG["actor_timeout_seconds"]
    
    await actor.initialize()
    assert actor.is_initialized
    assert actor.is_running


@pytest.mark.asyncio
async def test_handle_user_message_flow(mock_components):
    """Тест полного event-driven потока обработки сообщения"""
    actor = UserSessionActor(
        memory_actor=mock_components["memory_actor"],
        event_store=mock_components["event_store"]
    )
    await actor.initialize()
    
    # Тестируем обработку сообщения
    response = await actor.handle_user_message(
        user_message="Привет, Химера!",
        user_id=12345
    )
    
    assert response == "Тестовый ответ Химеры"
    
    # Проверяем, что события были сохранены
    assert mock_components["event_store"].save_event.call_count >= 2  # UserMessageEvent и BotResponseEvent
    
    # Проверяем вызовы MemoryActor
    memory_calls = mock_components["memory_actor"].handle_message.call_args_list
    assert len(memory_calls) >= 3  # store user message, get context, store bot response
    
    # Проверяем метрики
    assert actor._coordination_metrics["total_messages"] == 1
    assert actor._coordination_metrics["successful_flows"] == 1


@pytest.mark.asyncio
async def test_actor_coordination_timeout(mock_components):
    """Тест обработки timeout при координации акторов"""
    # Настраиваем memory_actor для timeout
    mock_components["memory_actor"].handle_message = AsyncMock(
        side_effect=asyncio.TimeoutError()
    )
    
    actor = UserSessionActor(
        memory_actor=mock_components["memory_actor"],
        event_store=mock_components["event_store"],
        config={**COORDINATION_CONFIG, "actor_timeout_seconds": 0.1}
    )
    await actor.initialize()
    
    # Тестируем с ожиданием ошибки
    response = await actor.handle_user_message(
        user_message="Тест timeout",
        user_id=12345
    )
    
    # Должен вернуть fallback ответ
    assert "Что-то пошло не так" in response
    assert actor._coordination_metrics["failed_flows"] == 1
    assert actor._coordination_metrics["actor_timeouts"] > 0


@pytest.mark.asyncio
async def test_health_check_with_metrics(mock_components):
    """Тест health check с метриками координации"""
    actor = UserSessionActor(
        memory_actor=mock_components["memory_actor"],
        event_store=mock_components["event_store"]
    )
    await actor.initialize()
    
    # Обрабатываем несколько сообщений для генерации метрик
    for i in range(3):
        await actor.handle_user_message(f"Сообщение {i}", user_id=12345)
    
    # Получаем health check
    health = await actor.health_check()
    
    assert health["actor"] == "user_session"
    assert health["status"] == "healthy"
    assert "coordination_metrics" in health
    
    metrics = health["coordination_metrics"]
    assert metrics["total_messages"] == 3
    assert metrics["successful_flows"] == 3
    assert metrics["success_rate"] == 1.0
    assert metrics["avg_response_time"] > 0