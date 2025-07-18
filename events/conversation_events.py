from typing import Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import validator
from events.base_event import BaseEvent
from config.events import EVENT_CONFIG


class UserMessageEvent(BaseEvent):
    """Событие сообщения пользователя"""
    
    event_type: Literal["user_message"] = "user_message"
    text: str
    emotion: Optional[str] = None      # Заготовка для PerceptionActor (этап 4)
    mode: Optional[str] = None         # Заготовка для системы ролей (этап 5)
    message_source: str = "telegram"   # Источник сообщения
    
    @validator('text')
    def validate_text_length(cls, v):
        """Валидация длины текста из конфига"""
        max_length = EVENT_CONFIG.get("event_types", {}).get("user_message", {}).get("max_text_length", 4096)
        if len(v) > max_length:
            raise ValueError(f"Text length {len(v)} exceeds limit {max_length}")
        return v
    
    def to_memory_format(self) -> Dict[str, Any]:
        """Преобразование для сохранения в MemoryActor"""
        return {
            "user_id": self.user_id,
            "content": self.text,
            "emotion": self.emotion,
            "mode": self.mode
        }


class BotResponseEvent(BaseEvent):
    """Событие ответа бота"""
    
    event_type: Literal["bot_response"] = "bot_response"
    response_text: str
    generation_time_ms: int
    mode_used: Optional[str] = None           # Заготовка для системы ролей (этап 5)
    injection_used: Optional[Dict] = None      # Заготовка для PersonalityActor (этап 8)
    
    @validator('response_text')
    def validate_response_length(cls, v):
        """Валидация длины ответа из конфига"""
        max_length = EVENT_CONFIG.get("event_types", {}).get("bot_response", {}).get("max_text_length", 8192)
        if len(v) > max_length:
            raise ValueError(f"Response length {len(v)} exceeds limit {max_length}")
        return v
    
    def to_memory_format(self) -> Dict[str, Any]:
        """Преобразование для сохранения в MemoryActor"""
        return {
            "user_id": self.user_id,
            "content": self.response_text,
            "mode": self.mode_used
        }


class SystemEvent(BaseEvent):
    """Системное событие для внутренних процессов"""
    
    event_type: Literal["system_event"] = "system_event"
    event_subtype: str  # Конкретный тип системного события
    severity: str = "info"  # info, warning, error, critical
    actor_name: Optional[str] = None
    
    @validator('severity')
    def validate_severity(cls, v):
        valid_severities = ["info", "warning", "error", "critical"]
        if v not in valid_severities:
            raise ValueError(f"Invalid severity: {v}")
        return v


class ActorCoordinationEvent(BaseEvent):
    """Событие координации между акторами"""
    
    event_type: Literal["actor_coordination"] = "actor_coordination"
    source_actor: str
    target_actor: str
    coordination_type: str  # request, response, timeout, error
    duration_ms: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        # Системные события не требуют user_id
        if self.user_id is None:
            self.stream_id = f"system_coordination_{self.source_actor}_{self.target_actor}"