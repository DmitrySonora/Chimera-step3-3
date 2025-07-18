import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

from actors.base_actor import BaseActor
from actors.message_types import ActorMessage, MEMORY_MESSAGE_TYPES
from database.connection import DatabaseConnection
from config.memory import MEMORY_CONFIG

logger = logging.getLogger(__name__)


class MemoryActor(BaseActor):
    """Актор управления кратковременной памятью (STM)"""
    
    def __init__(self, database_connection: DatabaseConnection):
        super().__init__("memory", MEMORY_CONFIG)
        self.db = database_connection
        
        # Параметры из конфига
        self.stm_limit = self.config["stm_limit"]
        self.cleanup_batch_size = self.config["cleanup_batch_size"]
        self.query_timeout = self.config["query_timeout_seconds"]
        self.retry_attempts = self.config["retry_attempts"]
        self.retry_delay = self.config["retry_delay_seconds"]
        self.context_max_length = self.config["context_max_length"]
        
        # Внутреннее состояние
        self._cleanup_tasks = {}
        self._performance_metrics = {
            "store_latency": [],
            "retrieve_latency": [],
            "cleanup_operations": 0
        }
    
    async def handle_message(self, message: Dict[str, Any]) -> Any:
        """Обработка типизированных сообщений"""
        try:
            self.increment_message_count()
            
            # Извлекаем тип сообщения
            if isinstance(message, ActorMessage):
                message_type = message.type
                data = message.data
            else:
                message_type = message.get('type')
                data = message.get('data', {})
            
            # Логируем если включено
            if self.config.get("performance_log_enabled"):
                self.logger.debug(f"Обработка сообщения: {message_type}")
            
            # Обрабатываем по типу
            if message_type == 'store_user_message':
                return await self._store_user_message(data)
            elif message_type == 'store_bot_response':
                return await self._store_bot_response(data)
            elif message_type == 'get_conversation_context':
                return await self._get_conversation_context(data)
            elif message_type == 'cleanup_old_messages':
                return await self._cleanup_old_messages(data)
            elif message_type == 'get_user_stats':
                return await self._get_user_stats(data)
            else:
                self.logger.warning(f"Неизвестный тип сообщения: {message_type}")
                return {"error": f"Unknown message type: {message_type}"}
                
        except Exception as e:
            self.increment_error_count()
            self.logger.error(f"Ошибка обработки сообщения: {e}")
            return {"error": str(e)}
    
    async def _store_user_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Сохранить сообщение пользователя в STM"""
        user_id = data['user_id']
        content = data['content']
        emotion = data.get('emotion')
        mode = data.get('mode')
        
        start_time = datetime.utcnow()
        
        try:
            # Retry логика из конфига
            for attempt in range(self.retry_attempts):
                try:
                    async with self.db.acquire() as conn:
                        # Сохраняем сообщение
                        message_id = await conn.fetchval("""
                            INSERT INTO stm_buffer (user_id, role, content, emotion, mode)
                            VALUES ($1, $2, $3, $4, $5)
                            RETURNING id
                        """, user_id, 'user', content, emotion, mode)
                        
                        # Запускаем cleanup если нужно
                        await self._check_and_cleanup(user_id)
                        
                        # Метрики производительности
                        if self.config.get("performance_log_enabled"):
                            latency = (datetime.utcnow() - start_time).total_seconds()
                            self._performance_metrics["store_latency"].append(latency)
                            if len(self._performance_metrics["store_latency"]) > 100:
                                self._performance_metrics["store_latency"].pop(0)
                        
                        return {
                            "success": True,
                            "message_id": message_id,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        
                except Exception as e:
                    if attempt < self.retry_attempts - 1:
                        await asyncio.sleep(self.retry_delay)
                        continue
                    raise e
                    
        except Exception as e:
            self.logger.error(f"Ошибка сохранения сообщения пользователя: {e}")
            return {"success": False, "error": str(e)}
    
    async def _store_bot_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Сохранить ответ бота в STM"""
        user_id = data['user_id']
        content = data['content']
        mode = data.get('mode')
        
        try:
            async with self.db.acquire() as conn:
                message_id = await conn.fetchval("""
                    INSERT INTO stm_buffer (user_id, role, content, mode)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id
                """, user_id, 'assistant', content, mode)
                
                return {
                    "success": True,
                    "message_id": message_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Ошибка сохранения ответа бота: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_conversation_context(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Получить контекст диалога из STM"""
        user_id = data['user_id']
        limit = data.get('limit', self.stm_limit)
        
        start_time = datetime.utcnow()
        
        try:
            async with self.db.acquire() as conn:
                # Получаем последние сообщения
                messages = await conn.fetch("""
                    SELECT id, role, content, emotion, mode, created_at
                    FROM stm_buffer
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """, user_id, limit)
                
                # Формируем контекст
                context_messages = []
                total_length = 0
                
                for msg in reversed(messages):  # Возвращаем в хронологическом порядке
                    message_dict = {
                        "id": msg['id'],
                        "role": msg['role'],
                        "content": msg['content'],
                        "emotion": msg['emotion'],
                        "mode": msg['mode'],
                        "timestamp": msg['created_at'].isoformat()
                    }
                    
                    # Проверяем лимит длины контекста
                    message_length = len(msg['content'])
                    if total_length + message_length > self.context_max_length:
                        break
                    
                    context_messages.append(message_dict)
                    total_length += message_length
                
                # Метрики производительности
                if self.config.get("performance_log_enabled"):
                    latency = (datetime.utcnow() - start_time).total_seconds()
                    self._performance_metrics["retrieve_latency"].append(latency)
                    if len(self._performance_metrics["retrieve_latency"]) > 100:
                        self._performance_metrics["retrieve_latency"].pop(0)
                
                return {
                    "success": True,
                    "messages": context_messages,
                    "count": len(context_messages),
                    "total_length": total_length
                }
                
        except Exception as e:
            self.logger.error(f"Ошибка получения контекста: {e}")
            return {"success": False, "error": str(e), "messages": []}
    
    async def _cleanup_old_messages(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Очистить старые сообщения (кольцевой буфер)"""
        user_id = data['user_id']
        
        try:
            async with self.db.acquire() as conn:
                # Получаем количество сообщений
                count = await conn.fetchval("""
                    SELECT COUNT(*) FROM stm_buffer WHERE user_id = $1
                """, user_id)
                
                if count > self.stm_limit:
                    # Удаляем старые сообщения
                    excess = count - self.stm_limit
                    deleted = await conn.execute("""
                        DELETE FROM stm_buffer
                        WHERE id IN (
                            SELECT id FROM stm_buffer
                            WHERE user_id = $1
                            ORDER BY created_at ASC
                            LIMIT $2
                        )
                    """, user_id, excess + self.cleanup_batch_size)
                    
                    self._performance_metrics["cleanup_operations"] += 1
                    
                    self.logger.info(f"Очищено {excess} старых сообщений для пользователя {user_id}")
                    
                    return {
                        "success": True,
                        "deleted_count": excess,
                        "remaining_count": self.stm_limit
                    }
                
                return {
                    "success": True,
                    "deleted_count": 0,
                    "remaining_count": count
                }
                
        except Exception as e:
            self.logger.error(f"Ошибка очистки сообщений: {e}")
            return {"success": False, "error": str(e)}
    
    async def _check_and_cleanup(self, user_id: int):
        """Проверить необходимость очистки и запустить при необходимости"""
        # Избегаем множественных cleanup для одного пользователя
        if user_id in self._cleanup_tasks:
            return
        
        try:
            async with self.db.acquire() as conn:
                count = await conn.fetchval("""
                    SELECT COUNT(*) FROM stm_buffer WHERE user_id = $1
                """, user_id)
                
                if count > self.stm_limit:
                    # Запускаем cleanup в фоне
                    task = asyncio.create_task(
                        self._cleanup_old_messages({"user_id": user_id})
                    )
                    self._cleanup_tasks[user_id] = task
                    
                    # Удаляем task после завершения
                    task.add_done_callback(
                        lambda t: self._cleanup_tasks.pop(user_id, None)
                    )
                    
        except Exception as e:
            self.logger.error(f"Ошибка проверки cleanup: {e}")
    
    async def _get_user_stats(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Получить статистику пользователя"""
        user_id = data['user_id']
        
        try:
            async with self.db.acquire() as conn:
                stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_messages,
                        COUNT(*) FILTER (WHERE role = 'user') as user_messages,
                        COUNT(*) FILTER (WHERE role = 'assistant') as bot_messages,
                        MIN(created_at) as first_message,
                        MAX(created_at) as last_message
                    FROM stm_buffer
                    WHERE user_id = $1
                """, user_id)
                
                return {
                    "success": True,
                    "user_id": user_id,
                    "total_messages": stats['total_messages'],
                    "user_messages": stats['user_messages'],
                    "bot_messages": stats['bot_messages'],
                    "first_message": stats['first_message'].isoformat() if stats['first_message'] else None,
                    "last_message": stats['last_message'].isoformat() if stats['last_message'] else None
                }
                
        except Exception as e:
            self.logger.error(f"Ошибка получения статистики: {e}")
            return {"success": False, "error": str(e)}
    
    async def _graceful_shutdown(self):
        """Graceful shutdown - ждем завершения cleanup задач"""
        if self._cleanup_tasks:
            self.logger.info(f"Ожидаем завершения {len(self._cleanup_tasks)} cleanup задач")
            await asyncio.gather(*self._cleanup_tasks.values(), return_exceptions=True)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Получить метрики производительности"""
        store_latency = self._performance_metrics["store_latency"]
        retrieve_latency = self._performance_metrics["retrieve_latency"]
        
        return {
            "store_latency_avg": sum(store_latency) / len(store_latency) if store_latency else 0,
            "retrieve_latency_avg": sum(retrieve_latency) / len(retrieve_latency) if retrieve_latency else 0,
            "cleanup_operations": self._performance_metrics["cleanup_operations"],
            "samples": {
                "store": len(store_latency),
                "retrieve": len(retrieve_latency)
            }
        }