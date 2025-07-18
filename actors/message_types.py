from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime
import uuid


@dataclass
class ActorMessage:
    """Базовый класс для всех сообщений между акторами"""
    type: str
    data: Dict[str, Any]
    sender: str = "unknown"
    request_id: str = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.request_id is None:
            self.request_id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


# Типы сообщений для MemoryActor
MEMORY_MESSAGE_TYPES = {
    "store_user_message": {
        "description": "Сохранить сообщение пользователя",
        "required_fields": ["user_id", "content"]
    },
    "store_bot_response": {
        "description": "Сохранить ответ бота",
        "required_fields": ["user_id", "content"]
    },
    "get_conversation_context": {
        "description": "Получить контекст диалога",
        "required_fields": ["user_id"]
    },
    "cleanup_old_messages": {
        "description": "Очистить старые сообщения",
        "required_fields": ["user_id"]
    },
    "get_user_stats": {
        "description": "Получить статистику пользователя",
        "required_fields": ["user_id"]
    }
}


def create_memory_message(message_type: str, data: Dict[str, Any], sender: str = "system") -> ActorMessage:
    """
    Создать типизированное сообщение для MemoryActor
    
    Args:
        message_type: Тип сообщения из MEMORY_MESSAGE_TYPES
        data: Данные сообщения
        sender: Отправитель сообщения
        
    Returns:
        ActorMessage объект
        
    Raises:
        ValueError: Если тип сообщения неизвестен или отсутствуют обязательные поля
    """
    if message_type not in MEMORY_MESSAGE_TYPES:
        raise ValueError(f"Неизвестный тип сообщения: {message_type}")
    
    # Проверяем обязательные поля
    required_fields = MEMORY_MESSAGE_TYPES[message_type]["required_fields"]
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        raise ValueError(f"Отсутствуют обязательные поля для {message_type}: {missing_fields}")
    
    return ActorMessage(type=message_type, data=data, sender=sender)