#!/usr/bin/env python3
"""
Скрипт создания и настройки базы данных Химера 2.0
"""
import asyncio
import sys
import logging
from pathlib import Path
import asyncpg

# Добавляем корневую папку проекта в path
sys.path.append(str(Path(__file__).parent.parent))

from config.database import DATABASE_CONFIG, DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_database():
    """Создание базы данных если она не существует"""
    # Подключаемся к postgres для создания БД
    conn_params = DATABASE_CONFIG.copy()
    db_name = conn_params.pop('database')
    
    try:
        # Подключаемся к системной БД postgres
        conn = await asyncpg.connect(
            host=conn_params['host'],
            port=conn_params['port'],
            user=conn_params['user'],
            password=conn_params['password'],
            database='postgres'
        )
        
        # Проверяем существование БД
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname = $1)",
            db_name
        )
        
        if not exists:
            # Создаем БД
            await conn.execute(f'CREATE DATABASE {db_name}')
            logger.info(f"База данных '{db_name}' создана")
        else:
            logger.info(f"База данных '{db_name}' уже существует")
        
        await conn.close()
        
    except Exception as e:
        logger.error(f"Ошибка при создании базы данных: {e}")
        raise


async def apply_schema():
    """Применение схемы базы данных"""
    try:
        # Подключаемся к нашей БД
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Читаем файл схемы
        schema_path = Path(__file__).parent.parent / 'database' / 'schema.sql'
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        # Применяем схему
        await conn.execute(schema_sql)
        logger.info("Схема базы данных применена успешно")
        
        # Проверяем созданные таблицы
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename IN ('events', 'stm_buffer')
        """)
        
        for table in tables:
            logger.info(f"✓ Таблица '{table['tablename']}' создана")
        
        # Проверяем индексы
        indexes = await conn.fetch("""
            SELECT indexname FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND tablename IN ('events', 'stm_buffer')
        """)
        
        logger.info(f"Создано {len(indexes)} индексов")
        
        await conn.close()
        
    except Exception as e:
        logger.error(f"Ошибка при применении схемы: {e}")
        raise


async def verify_setup():
    """Проверка корректности установки"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Тестовые операции
        # 1. Вставка в events
        await conn.execute("""
            INSERT INTO events (event_type, user_id, data, stream_id)
            VALUES ('test_event', 1, '{"test": true}'::jsonb, 'test_stream')
        """)
        
        # 2. Вставка в stm_buffer
        await conn.execute("""
            INSERT INTO stm_buffer (user_id, role, content)
            VALUES (1, 'user', 'Тестовое сообщение')
        """)
        
        # 3. Проверка чтения
        event_count = await conn.fetchval("SELECT COUNT(*) FROM events")
        stm_count = await conn.fetchval("SELECT COUNT(*) FROM stm_buffer")
        
        logger.info(f"✓ Тестовые данные созданы: {event_count} событий, {stm_count} сообщений")
        
        # 4. Очистка тестовых данных
        await conn.execute("DELETE FROM events WHERE event_type = 'test_event'")
        await conn.execute("DELETE FROM stm_buffer WHERE content = 'Тестовое сообщение'")
        
        logger.info("✓ База данных работает корректно")
        
        await conn.close()
        
    except Exception as e:
        logger.error(f"Ошибка при проверке: {e}")
        raise


async def main():
    """Основная функция"""
    logger.info("=== Настройка базы данных Химера 2.0 ===")
    
    try:
        # 1. Создаем БД
        logger.info("\n1. Создание базы данных...")
        await create_database()
        
        # 2. Применяем схему
        logger.info("\n2. Применение схемы...")
        await apply_schema()
        
        # 3. Проверяем работу
        logger.info("\n3. Проверка установки...")
        await verify_setup()
        
        logger.info("\n✅ База данных успешно настроена!")
        
    except Exception as e:
        logger.error(f"\n❌ Ошибка настройки: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())