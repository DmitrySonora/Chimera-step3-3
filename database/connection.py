import asyncio
import logging
from typing import Optional, Any, Dict, List
import asyncpg
from asyncpg import Pool, Connection
from contextlib import asynccontextmanager

from config.database import (
    DATABASE_URL,
    POOL_MIN_SIZE,
    POOL_MAX_SIZE,
    POOL_MAX_INACTIVE_CONNECTION_LIFETIME,
    QUERY_TIMEOUT,
    STATEMENT_TIMEOUT
)

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Управление подключениями к PostgreSQL с поддержкой connection pooling"""
    
    def __init__(self):
        self.pool: Optional[Pool] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Инициализация connection pool"""
        if self._initialized:
            logger.warning("❗️Подключение к БД уже установлено")
            return
        
        try:
            # Создаем connection pool
            self.pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=POOL_MIN_SIZE,
                max_size=POOL_MAX_SIZE,
                max_inactive_connection_lifetime=POOL_MAX_INACTIVE_CONNECTION_LIFETIME,
                command_timeout=QUERY_TIMEOUT,
                statement_cache_size=0,  # Отключаем кэш для гибкости
            )
            
            # Проверяем подключение
            async with self.pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                logger.info(f"🐲 Содинение с PostgreSQL: {version}")
            
            self._initialized = True
            logger.info("🐲 Пул подключений к БД инициализирован")
            
        except Exception as e:
            logger.error(f"❌ Невозможно подключиться к БД: {e}")
            raise
    
    async def close(self) -> None:
        """Закрытие connection pool"""
        if self.pool:
            await self.pool.close()
            self._initialized = False
            logger.info("🐲 Пул подключений к БД закрыт")
    
    @asynccontextmanager
    async def acquire(self):
        """Получение соединения из pool"""
        if not self.pool:
            raise RuntimeError("Database connection not initialized")
        
        async with self.pool.acquire() as connection:
            # Устанавливаем timeout для statements
            await connection.execute(
                f"SET statement_timeout = {STATEMENT_TIMEOUT * 1000}"
            )
            yield connection
    
    async def execute(self, query: str, *args) -> str:
        """Выполнение запроса без возврата результата"""
        async with self.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args) -> List[asyncpg.Record]:
        """Выполнение запроса с возвратом множества строк"""
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Выполнение запроса с возвратом одной строки"""
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args) -> Any:
        """Выполнение запроса с возвратом одного значения"""
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args)
    
    async def execute_many(self, query: str, args_list: List[tuple]) -> None:
        """Выполнение множественных запросов (batch)"""
        async with self.acquire() as conn:
            await conn.executemany(query, args_list)
    
    async def transaction(self, isolation_level: str = "read_committed"):
        """Контекстный менеджер для транзакций"""
        async with self.acquire() as conn:
            async with conn.transaction(isolation=isolation_level):
                yield conn


# Глобальный экземпляр для использования в проекте
db = DatabaseConnection()