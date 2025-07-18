from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, validator
import uuid
import json
import sys
from config.events import EVENT_CONFIG


class BaseEvent(BaseModel):
    """Базовый класс для всех событий системы с конфигурируемой валидацией"""
    
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[int] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    
    # Расширенные поля для Event Sourcing
    stream_id: Optional[str] = None
    version: int = 1
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def __init__(self, **data):
        super().__init__(**data)
        # Генерируем stream_id на основе конфига
        if self.stream_id is None and self.user_id is not None:
            stream_format = EVENT_CONFIG.get("stream_id_format", "user_{user_id}")
            self.stream_id = stream_format.format(user_id=self.user_id)
    
    @validator('event_type')
    def validate_event_type(cls, v):
        """Валидация типа события из конфигурации"""
        if EVENT_CONFIG.get("event_validation_enabled", True):
            valid_types = EVENT_CONFIG.get("event_types", {})
            if v not in valid_types and not v.startswith("system."):
                # Разрешаем системные события с префиксом system.
                raise ValueError(f"Unknown event type: {v}")
        return v
    
    @validator('metadata')
    def validate_metadata_size(cls, v):
        """Валидация размера метаданных"""
        if EVENT_CONFIG.get("event_validation_enabled", True):
            max_size = EVENT_CONFIG.get("event_metadata_max_size", 1024)
            metadata_str = json.dumps(v)
            if len(metadata_str) > max_size:
                raise ValueError(f"Metadata size {len(metadata_str)} exceeds limit {max_size}")
        return v
    
    def validate_event_size(self):
        """Валидация общего размера события"""
        if not EVENT_CONFIG.get("event_validation_enabled", True):
            return
        
        max_size = EVENT_CONFIG.get("max_event_size_bytes", 64000)
        event_size = sys.getsizeof(self.json())
        
        if event_size > max_size:
            if EVENT_CONFIG.get("event_compression_enabled", True):
                # В будущем здесь будет сжатие
                pass
            else:
                raise ValueError(f"Event size {event_size} exceeds limit {max_size}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация для хранения в БД"""
        data = self.dict()
        # Преобразуем datetime в ISO формат для БД
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseEvent':
        """Десериализация из БД"""
        # Преобразуем ISO строку обратно в datetime
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)
    
    def add_metadata(self, key: str, value: Any):
        """Добавить метаданные к событию"""
        self.metadata[key] = value
        # Проверяем размер после добавления
        self.validate_metadata_size(self.metadata)