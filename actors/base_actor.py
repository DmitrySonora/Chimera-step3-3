from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseActor(ABC):
    """Базовый класс для всех акторов системы"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"actor.{name}")
        self.is_initialized = False
        self.is_running = False
        self._start_time: Optional[datetime] = None
        self._message_count = 0
        self._error_count = 0
        
        # Конфигурация из общих настроек
        from config.actors import ACTOR_CONFIG
        self.actor_config = ACTOR_CONFIG
        
        self.logger.info(f"🐲 Создан актор: {self.name}")
    
    @abstractmethod
    async def handle_message(self, message: Dict[str, Any]) -> Any:
        """
        Обработка входящего сообщения
        
        Args:
            message: Словарь с типом сообщения и данными
            
        Returns:
            Результат обработки сообщения
        """
        pass
    
    async def initialize(self):
        """Инициализация актора при запуске"""
        if self.is_initialized:
            self.logger.warning(f"🐲 Актор {self.name} уже инициализирован")
            return
        
        self._start_time = datetime.utcnow()
        self.is_initialized = True
        self.is_running = True
        self.logger.info(f"🐲 Актор {self.name} инициализирован")
    
    async def shutdown(self):
        """Корректное завершение работы актора"""
        if not self.is_running:
            return
        
        self.logger.info(f"🐲 Начинаем остановку актора {self.name}")
        
        # Graceful shutdown с таймаутом из конфига
        timeout = self.actor_config.get("graceful_shutdown_timeout", 30)
        try:
            await asyncio.wait_for(self._graceful_shutdown(), timeout=timeout)
        except asyncio.TimeoutError:
            self.logger.error(f"Таймаут при остановке актора {self.name}")
        
        self.is_running = False
        self.is_initialized = False
        self.logger.info(f"🐲 Актор {self.name} остановлен")
    
    async def _graceful_shutdown(self):
        """Переопределяется в наследниках для специфичной логики"""
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check для системного мониторинга"""
        uptime = None
        if self._start_time:
            uptime = (datetime.utcnow() - self._start_time).total_seconds()
        
        return {
            "actor": self.name,
            "status": "healthy" if self.is_running else "stopped",
            "initialized": self.is_initialized,
            "uptime_seconds": uptime,
            "message_count": self._message_count,
            "error_count": self._error_count,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def increment_message_count(self):
        """Увеличить счетчик обработанных сообщений"""
        self._message_count += 1
    
    def increment_error_count(self):
        """Увеличить счетчик ошибок"""
        self._error_count += 1