import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from events.base_event import BaseEvent
from config.events import EVENT_CONFIG

logger = logging.getLogger(__name__)


class EventLogger:
    """Сервис для структурированного логирования событий"""
    
    def __init__(self, log_level: str = "INFO"):
        self.logger = logging.getLogger("events")
        self.logger.setLevel(getattr(logging, log_level))
        
        # Создаем форматтер для структурированных логов
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Настраиваем handler если еще не настроен
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        
        self._event_counts = {}
        self._error_counts = {}
    
    def log_event(self, event: BaseEvent, level: str = "INFO"):
        """Логировать событие"""
        # Инкрементируем счетчик событий
        event_type = event.event_type
        self._event_counts[event_type] = self._event_counts.get(event_type, 0) + 1
        
        # Форматируем сообщение
        log_data = {
            "event_id": event.event_id,
            "event_type": event_type,
            "user_id": event.user_id,
            "timestamp": event.timestamp.isoformat(),
            "stream_id": event.stream_id
        }
        
        # Добавляем важные поля из data
        if event_type == "user_message":
            log_data["text_preview"] = event.data.get("text", "")[:50] + "..."
        elif event_type == "bot_response":
            log_data["generation_time_ms"] = event.data.get("generation_time_ms")
            log_data["mode_used"] = event.data.get("mode_used")
        
        # Логируем
        log_message = f"EVENT: {json.dumps(log_data, ensure_ascii=False)}"
        getattr(self.logger, level.lower())(log_message)
    
    def log_error(self, event_type: str, error: Exception, context: Dict[str, Any] = None):
        """Логировать ошибку, связанную с событием"""
        # Инкрементируем счетчик ошибок
        self._error_counts[event_type] = self._error_counts.get(event_type, 0) + 1
        
        error_data = {
            "event_type": event_type,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if context:
            error_data["context"] = context
        
        self.logger.error(f"EVENT_ERROR: {json.dumps(error_data, ensure_ascii=False)}")
    
    def log_coordination(
        self, 
        source_actor: str, 
        target_actor: str, 
        action: str,
        duration_ms: Optional[int] = None,
        success: bool = True
    ):
        """Логировать координацию между акторами"""
        coord_data = {
            "type": "actor_coordination",
            "source": source_actor,
            "target": target_actor,
            "action": action,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if duration_ms is not None:
            coord_data["duration_ms"] = duration_ms
        
        level = "INFO" if success else "WARNING"
        getattr(self.logger, level.lower())(
            f"COORDINATION: {json.dumps(coord_data, ensure_ascii=False)}"
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику событий"""
        total_events = sum(self._event_counts.values())
        total_errors = sum(self._error_counts.values())
        
        return {
            "total_events": total_events,
            "total_errors": total_errors,
            "event_counts": self._event_counts.copy(),
            "error_counts": self._error_counts.copy(),
            "error_rate": total_errors / total_events if total_events > 0 else 0
        }
    
    def log_event_flow(self, flow_id: str, steps: List[Dict[str, Any]]):
        """Логировать полный event flow"""
        flow_data = {
            "flow_id": flow_id,
            "steps": len(steps),
            "duration_ms": sum(s.get("duration_ms", 0) for s in steps),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.logger.info(f"EVENT_FLOW: {json.dumps(flow_data, ensure_ascii=False)}")
        
        # Детальный лог каждого шага если включен debug
        if self.logger.level <= logging.DEBUG:
            for i, step in enumerate(steps):
                self.logger.debug(f"  Step {i+1}: {json.dumps(step, ensure_ascii=False)}")


# Глобальный экземпляр логгера событий
event_logger = EventLogger()