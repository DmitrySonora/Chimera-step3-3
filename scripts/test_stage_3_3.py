#!/usr/bin/env python3
"""
Скрипт проверки этапа 3.3 - Event Sourcing + координация акторов
"""
import asyncio
import sys
import logging
from pathlib import Path

# Добавляем корневую папку проекта в path
sys.path.append(str(Path(__file__).parent.parent))

from database.connection import db
from events.event_store import EventStore
from events.conversation_events import UserMessageEvent, BotResponseEvent
from actors.memory_actor import MemoryActor
from actors.user_session_actor import UserSessionActor
from config.events import EVENT_CONFIG
from config.coordination import COORDINATION_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_event_sourcing():
    """Тест Event Sourcing функциональности"""
    logger.info("\n=== Тест Event Sourcing ===")
    
    # Инициализация
    await db.initialize()
    event_store = EventStore(db)
    await event_store.initialize()
    
    try:
        # Создаем и сохраняем события
        user_event = UserMessageEvent(
            user_id=77777,
            text="Тестовое сообщение для проверки Event Sourcing",
            emotion="curious"
        )
        
        bot_event = BotResponseEvent(
            user_id=77777,
            response_text="Тестовый ответ системы",
            generation_time_ms=150,
            mode_used="default"
        )
        
        # Сохраняем
        logger.info("📝 Сохраняем события...")
        await event_store.save_event(user_event)
        await event_store.save_event(bot_event)
        
        # Форсируем запись
        await event_store._flush_buffer()
        
        # Читаем события
        logger.info("📖 Читаем события из БД...")
        events = await event_store.get_user_events(77777)
        
        logger.info(f"✅ Найдено событий: {len(events)}")
        for event in events[:2]:  # Показываем первые 2
            logger.info(f"  - {event['event_type']}: {event['data']}")
        
        # Очистка
        async with db.acquire() as conn:
            await conn.execute("DELETE FROM events WHERE user_id = 77777")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в тесте Event Sourcing: {e}")
        return False
    finally:
        await event_store.shutdown()


async def test_actor_coordination():
    """Тест координации акторов"""
    logger.info("\n=== Тест координации акторов ===")
    
    try:
        # Инициализация компонентов
        event_store = EventStore(db)
        await event_store.initialize()
        
        memory_actor = MemoryActor(db)
        await memory_actor.initialize()
        
        user_session_actor = UserSessionActor(memory_actor, event_store)
        await user_session_actor.initialize()
        
        # Тестовое сообщение
        logger.info("💬 Отправляем тестовое сообщение...")
        response = await user_session_actor.handle_user_message(
            "Привет, это тест координации акторов!",
            user_id=77777
        )
        
        logger.info(f"✅ Получен ответ: {response[:100]}...")
        
        # Проверяем метрики
        health = await user_session_actor.health_check()
        metrics = health.get("coordination_metrics", {})
        
        logger.info("📊 Метрики координации:")
        logger.info(f"  - Обработано сообщений: {metrics.get('total_messages', 0)}")
        logger.info(f"  - Успешных потоков: {metrics.get('successful_flows', 0)}")
        logger.info(f"  - Success rate: {metrics.get('success_rate', 0):.2%}")
        
        # Очистка
        async with db.acquire() as conn:
            await conn.execute("DELETE FROM events WHERE user_id = 77777")
            await conn.execute("DELETE FROM stm_buffer WHERE user_id = 77777")
        
        # Shutdown
        await user_session_actor.shutdown()
        await memory_actor.shutdown()
        await event_store.shutdown()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в тесте координации: {e}")
        return False


async def test_configuration():
    """Тест загрузки конфигурации"""
    logger.info("\n=== Тест конфигурации ===")
    
    # Проверяем EVENT_CONFIG
    logger.info("📋 Проверка EVENT_CONFIG:")
    assert "max_event_size_bytes" in EVENT_CONFIG
    assert "event_types" in EVENT_CONFIG
    logger.info(f"  ✅ Максимальный размер события: {EVENT_CONFIG['max_event_size_bytes']} байт")
    logger.info(f"  ✅ Типов событий: {len(EVENT_CONFIG['event_types'])}")
    
    # Проверяем COORDINATION_CONFIG
    logger.info("\n📋 Проверка COORDINATION_CONFIG:")
    assert "actor_timeout_seconds" in COORDINATION_CONFIG
    assert "coordination_patterns" in COORDINATION_CONFIG
    logger.info(f"  ✅ Timeout акторов: {COORDINATION_CONFIG['actor_timeout_seconds']} сек")
    logger.info(f"  ✅ Retry попыток: {COORDINATION_CONFIG['coordination_retry_attempts']}")
    
    return True


async def main():
    """Основная функция тестирования"""
    logger.info("🐲 Тестирование этапа 3.3: Event Sourcing + координация акторов")
    
    results = []
    
    try:
        # 1. Тест конфигурации
        results.append(("Конфигурация", await test_configuration()))
        
        # 2. Тест Event Sourcing
        results.append(("Event Sourcing", await test_event_sourcing()))
        
        # 3. Тест координации
        results.append(("Координация акторов", await test_actor_coordination()))
        
        # Итоги
        logger.info("\n=== ИТОГИ ТЕСТИРОВАНИЯ ===")
        all_passed = True
        for test_name, passed in results:
            status = "✅ PASS" if passed else "❌ FAIL"
            logger.info(f"{test_name}: {status}")
            if not passed:
                all_passed = False
        
        if all_passed:
            logger.info("\n🎉 Все тесты пройдены успешно! Этап 3.3 завершен.")
        else:
            logger.info("\n⚠️ Некоторые тесты не пройдены. Проверьте логи.")
        
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())