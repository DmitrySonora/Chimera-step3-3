import logging
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio
from database.connection import DatabaseConnection
from events.base_event import BaseEvent
from config.events import EVENT_CONFIG
from config.coordination import COORDINATION_CONFIG

logger = logging.getLogger(__name__)


class EventStore:
    """Простой Event Store для сохранения и извлечения событий"""
    
    def __init__(self, db: DatabaseConnection):
        self.db = db
        self._event_buffer = []
        self._buffer_lock = asyncio.Lock()
        self._flush_task = None
        self.batch_size = EVENT_CONFIG.get("event_batch_size", 100)
        
    async def initialize(self):
        """Инициализация Event Store"""
        logger.info("🗄️ Инициализация Event Store")
        # Запускаем фоновую задачу для flush буфера
        self._flush_task = asyncio.create_task(self._periodic_flush())
        
    async def save_event(self, event: BaseEvent) -> bool:
        """Сохранить событие в store"""
        try:
            # Валидация размера события
            event.validate_event_size()
            
            # Добавляем в буфер для batch записи
            async with self._buffer_lock:
                self._event_buffer.append(event)
                
                # Если буфер заполнен, сохраняем
                if len(self._event_buffer) >= self.batch_size:
                    await self._flush_buffer()
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения события: {e}")
            return False
    
    async def _flush_buffer(self):
        """Сохранить буфер событий в БД"""
        if not self._event_buffer:
            return
        
        events_to_save = self._event_buffer.copy()
        self._event_buffer.clear()
        
        try:
            # Подготавливаем данные для batch insert
            event_data = []
            for event in events_to_save:
                event_dict = event.to_dict()
                event_data.append((
                    event_dict['event_type'],
                    event_dict['user_id'] or 0,  # 0 для системных событий
                    json.dumps(event_dict['data']),
                    event_dict['stream_id'] or '',
                    event_dict['version'],
                    json.dumps(event_dict['metadata'])
                ))
            
            # Batch insert
            await self.db.execute_many("""
                INSERT INTO events (event_type, user_id, data, stream_id, version, metadata)
                VALUES ($1, $2, $3::jsonb, $4, $5, $6::jsonb)
            """, event_data)
            
            logger.debug(f"✅ Сохранено {len(events_to_save)} событий")
            
        except Exception as e:
            logger.error(f"Ошибка при flush буфера: {e}")
            # Возвращаем события обратно в буфер
            async with self._buffer_lock:
                self._event_buffer = events_to_save + self._event_buffer
    
    async def _periodic_flush(self):
        """Периодическое сохранение буфера"""
        while True:
            await asyncio.sleep(5)  # Flush каждые 5 секунд
            async with self._buffer_lock:
                if self._event_buffer:
                    await self._flush_buffer()
    
    async def get_events_by_stream(
        self, 
        stream_id: str, 
        limit: int = 100,
        after_timestamp: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Получить события по stream_id"""
        try:
            query = """
                SELECT * FROM events 
                WHERE stream_id = $1
            """
            params = [stream_id]
            
            if after_timestamp:
                query += " AND timestamp > $2"
                params.append(after_timestamp)
            
            query += " ORDER BY timestamp ASC LIMIT $" + str(len(params) + 1)
            params.append(limit)
            
            rows = await self.db.fetch(query, *params)
            
            events = []
            for row in rows:
                event_data = dict(row)
                event_data['data'] = json.loads(event_data['data'])
                event_data['metadata'] = json.loads(event_data['metadata'])
                events.append(event_data)
            
            return events
            
        except Exception as e:
            logger.error(f"Ошибка получения событий: {e}")
            return []
    
    async def get_user_events(
        self, 
        user_id: int, 
        event_types: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Получить события пользователя"""
        try:
            query = "SELECT * FROM events WHERE user_id = $1"
            params = [user_id]
            
            if event_types:
                placeholders = ','.join([f'${i+2}' for i in range(len(event_types))])
                query += f" AND event_type IN ({placeholders})"
                params.extend(event_types)
            
            query += " ORDER BY timestamp DESC LIMIT $" + str(len(params) + 1)
            params.append(limit)
            
            rows = await self.db.fetch(query, *params)
            
            events = []
            for row in rows:
                event_data = dict(row)
                event_data['data'] = json.loads(event_data['data'])
                event_data['metadata'] = json.loads(event_data['metadata'])
                events.append(event_data)
            
            return events
            
        except Exception as e:
            logger.error(f"Ошибка получения событий пользователя: {e}")
            return []
    
    async def cleanup_old_events(self):
        """Очистка старых событий на основе retention policy"""
        retention_days = EVENT_CONFIG.get("event_retention_days", 365)
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        try:
            deleted = await self.db.execute("""
                DELETE FROM events 
                WHERE timestamp < $1 
                AND event_type NOT IN ('system_event', 'actor_coordination')
            """, cutoff_date)
            
            logger.info(f"🧹 Удалено старых событий: {deleted}")
            
        except Exception as e:
            logger.error(f"Ошибка очистки событий: {e}")
    
    async def shutdown(self):
        """Корректное завершение работы"""
        if self._flush_task:
            self._flush_task.cancel()
            
        # Финальный flush буфера
        async with self._buffer_lock:
            await self._flush_buffer()
        
        logger.info("🗄️ Event Store остановлен")