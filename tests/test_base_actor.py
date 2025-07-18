import pytest
import asyncio
from typing import Dict, Any

from actors.base_actor import BaseActor


class TestActor(BaseActor):
    """Тестовый актор для проверки BaseActor"""
    
    async def handle_message(self, message: Dict[str, Any]) -> Any:
        self.increment_message_count()
        
        if message.get("type") == "error":
            self.increment_error_count()
            raise Exception("Test error")
        
        return {"result": "ok", "data": message}


@pytest.mark.asyncio
async def test_actor_lifecycle():
    """Тест жизненного цикла актора"""
    config = {"test_param": "value"}
    actor = TestActor("test", config)
    
    # Проверяем начальное состояние
    assert actor.name == "test"
    assert actor.config == config
    assert not actor.is_initialized
    assert not actor.is_running
    
    # Инициализация
    await actor.initialize()
    assert actor.is_initialized
    assert actor.is_running
    
    # Повторная инициализация не должна ничего ломать
    await actor.initialize()
    assert actor.is_initialized
    
    # Shutdown
    await actor.shutdown()
    assert not actor.is_running
    assert not actor.is_initialized


@pytest.mark.asyncio
async def test_message_handling():
    """Тест обработки сообщений"""
    actor = TestActor("test", {})
    await actor.initialize()
    
    # Успешная обработка
    result = await actor.handle_message({"type": "test", "data": "hello"})
    assert result["result"] == "ok"
    assert actor._message_count == 1
    assert actor._error_count == 0
    
    # Обработка с ошибкой
    with pytest.raises(Exception):
        await actor.handle_message({"type": "error"})
    
    assert actor._message_count == 2
    assert actor._error_count == 1
    
    await actor.shutdown()


@pytest.mark.asyncio
async def test_health_check():
    """Тест health check"""
    actor = TestActor("test", {})
    
    # До инициализации
    health = await actor.health_check()
    assert health["actor"] == "test"
    assert health["status"] == "stopped"
    assert not health["initialized"]
    
    # После инициализации
    await actor.initialize()
    await asyncio.sleep(0.1)  # Даем время для установки времени старта
    
    health = await actor.health_check()
    assert health["status"] == "healthy"
    assert health["initialized"]
    assert health["uptime_seconds"] > 0
    
    await actor.shutdown()