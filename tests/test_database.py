import pytest
import asyncio
import json
from datetime import datetime
import sys
from pathlib import Path

# Добавляем корневую папку в path
sys.path.append(str(Path(__file__).parent.parent))

from database.connection import DatabaseConnection
from config.database import DATABASE_URL


class TestDatabase:
    """Тесты для базы данных с правильным управлением соединениями"""
    
    @pytest.fixture
    async def db_connection(self):
        """Создаем новое подключение для каждого теста"""
        db = DatabaseConnection()
        await db.initialize()
        yield db
        await db.close()
    
    @pytest.mark.asyncio
    async def test_database_connection(self, db_connection):
        """Тест подключения к базе данных"""
        # Проверяем, что pool создан
        assert db_connection.pool is not None
        assert db_connection._initialized is True
        
        # Проверяем выполнение простого запроса
        result = await db_connection.fetchval("SELECT 1")
        assert result == 1
    
    @pytest.mark.asyncio
    async def test_events_table_operations(self, db_connection):
        """Тест операций с таблицей events"""
        # Подготовка тестовых данных
        test_event = {
            "event_type": "test_message",
            "user_id": 12345,
            "data": {"text": "Тестовое сообщение", "metadata": {"source": "test"}},
            "stream_id": "test_stream_001"
        }
        
        # 1. Вставка события
        event_id = await db_connection.fetchval("""
            INSERT INTO events (event_type, user_id, data, stream_id)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """, test_event["event_type"], test_event["user_id"], 
            json.dumps(test_event["data"]), test_event["stream_id"])
        
        assert event_id is not None
        
        # 2. Чтение события
        event = await db_connection.fetchrow("""
            SELECT event_type, user_id, data::text, stream_id FROM events WHERE id = $1
        """, event_id)
        
        event_data = json.loads(event["data"])
        
        assert event["event_type"] == test_event["event_type"]
        assert event["user_id"] == test_event["user_id"]
        assert event_data["text"] == test_event["data"]["text"]
        assert event["stream_id"] == test_event["stream_id"]

        
        # 3. Проверка JSONB операций
        text_from_json = await db_connection.fetchval("""
            SELECT data->>'text' FROM events WHERE id = $1
        """, event_id)
        
        assert text_from_json == test_event["data"]["text"]
        
        # 4. Очистка
        await db_connection.execute("DELETE FROM events WHERE id = $1", event_id)
    
    @pytest.mark.asyncio
    async def test_stm_buffer_operations(self, db_connection):
        """Тест операций с таблицей stm_buffer"""
        test_message = {
            "user_id": 12345,
            "role": "user",
            "content": "Привет, Химера!",
            "emotion": "curious",
            "mode": "talk"
        }
        
        # 1. Вставка сообщения
        message_id = await db_connection.fetchval("""
            INSERT INTO stm_buffer (user_id, role, content, emotion, mode)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """, test_message["user_id"], test_message["role"], 
            test_message["content"], test_message["emotion"], test_message["mode"])
        
        assert message_id is not None
        
        # 2. Чтение последних сообщений пользователя
        messages = await db_connection.fetch("""
            SELECT * FROM stm_buffer 
            WHERE user_id = $1 
            ORDER BY created_at DESC 
            LIMIT 5
        """, test_message["user_id"])
        
        assert len(messages) > 0
        assert messages[0]["content"] == test_message["content"]
        assert messages[0]["emotion"] == test_message["emotion"]
        
        # 3. Очистка
        await db_connection.execute("DELETE FROM stm_buffer WHERE id = $1", message_id)
    
    @pytest.mark.asyncio
    async def test_index_performance(self, db_connection):
        """Тест производительности индексов"""
        import time
        
        # Создаем тестовые данные
        test_user_id = 99999
        events_data = []
        
        for i in range(100):
            events_data.append((
                f"perf_test_{i % 5}",
                test_user_id,
                json.dumps({"index": i, "test": True}),
                f"perf_stream_{i % 10}"
            ))
        
        # Вставляем данные
        await db_connection.execute_many("""
            INSERT INTO events (event_type, user_id, data, stream_id)
            VALUES ($1, $2, $3, $4)
        """, events_data)
        
        # Тест 1: Запрос с использованием индекса по user_id и timestamp
        start_time = time.time()
        result = await db_connection.fetch("""
            SELECT * FROM events 
            WHERE user_id = $1 
            ORDER BY timestamp DESC 
            LIMIT 10
        """, test_user_id)
        indexed_time = time.time() - start_time
        
        assert len(result) == 10
        assert indexed_time < 0.1  # Должно выполняться быстро
        
        # Тест 2: Запрос с использованием JSONB индекса
        start_time = time.time()
        result = await db_connection.fetch("""
            SELECT * FROM events 
            WHERE data @> '{"test": true}'::jsonb
            AND user_id = $1
            LIMIT 5
        """, test_user_id)
        jsonb_time = time.time() - start_time
        
        assert len(result) == 5
        assert jsonb_time < 0.2  # JSONB запросы могут быть медленнее
        
        # Очистка
        await db_connection.execute(
            "DELETE FROM events WHERE user_id = $1", 
            test_user_id
        )
        
        print(f"\n✓ Производительность индексов:")
        print(f"  - Индекс user_id + timestamp: {indexed_time:.3f}s")
        print(f"  - JSONB GIN индекс: {jsonb_time:.3f}s")
    
    @pytest.mark.asyncio
    async def test_transaction_handling(self, db_connection):
        """Тест работы транзакций"""
        test_user_id = 88888
        
        # Тест успешной транзакции
        async with db_connection.acquire() as conn:
            async with conn.transaction():
                # Вставляем событие
                await conn.execute("""
                    INSERT INTO events (event_type, user_id, data)
                    VALUES ('transaction_test', $1, '{"step": 1}'::jsonb)
                """, test_user_id)
                
                # Вставляем сообщение
                await conn.execute("""
                    INSERT INTO stm_buffer (user_id, role, content)
                    VALUES ($1, 'user', 'Транзакционное сообщение')
                """, test_user_id)
        
        # Проверяем, что данные сохранились
        event_count = await db_connection.fetchval(
            "SELECT COUNT(*) FROM events WHERE user_id = $1", 
            test_user_id
        )
        assert event_count == 1
        
        # Тест отката транзакции при ошибке
        try:
            async with db_connection.acquire() as conn:
                async with conn.transaction():
                    # Вставляем еще одно событие
                    await conn.execute("""
                        INSERT INTO events (event_type, user_id, data)
                        VALUES ('rollback_test', $1, '{"step": 2}'::jsonb)
                    """, test_user_id)
                    
                    # Вызываем ошибку
                    raise Exception("Тестовая ошибка для отката")
                    
        except Exception:
            pass  # Ожидаемая ошибка
        
        # Проверяем, что второе событие не сохранилось
        event_count = await db_connection.fetchval(
            "SELECT COUNT(*) FROM events WHERE user_id = $1", 
            test_user_id
        )
        assert event_count == 1  # Только первое событие
        
        # Очистка
        await db_connection.execute(
            "DELETE FROM events WHERE user_id = $1", 
            test_user_id
        )
        await db_connection.execute(
            "DELETE FROM stm_buffer WHERE user_id = $1", 
            test_user_id
        )


if __name__ == "__main__":
    # Запуск тестов из командной строки
    pytest.main([__file__, "-v", "-s"])