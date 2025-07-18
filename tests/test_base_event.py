import pytest
from datetime import datetime
import json
from events.base_event import BaseEvent
from events.conversation_events import UserMessageEvent, BotResponseEvent
from config.events import EVENT_CONFIG


class TestBaseEvent:
    """Тесты базового класса событий"""
    
    def test_base_event_creation(self):
        """Тест создания базового события"""
        event = BaseEvent(
            event_type="test_event",
            user_id=12345,
            data={"test": "data"}
        )
        
        assert event.event_type == "test_event"
        assert event.user_id == 12345
        assert event.data == {"test": "data"}
        assert event.event_id is not None
        assert event.version == 1
        assert isinstance(event.timestamp, datetime)
    
    def test_stream_id_generation(self):
        """Тест автоматической генерации stream_id"""
        event = BaseEvent(
            event_type="test_event",
            user_id=12345,
            data={}
        )
        
        expected_stream_id = EVENT_CONFIG["stream_id_format"].format(user_id=12345)
        assert event.stream_id == expected_stream_id
    
    def test_metadata_validation(self):
        """Тест валидации размера метаданных"""
        # Создаем большие метаданные
        large_metadata = {"data": "x" * 2000}
        
        with pytest.raises(ValueError) as exc_info:
            event = BaseEvent(
                event_type="test_event",
                user_id=12345,
                data={},
                metadata=large_metadata
            )
        assert "Metadata size" in str(exc_info.value)
    
    def test_event_serialization(self):
        """Тест сериализации события"""
        event = BaseEvent(
            event_type="test_event",
            user_id=12345,
            data={"message": "Hello"},
            metadata={"source": "test"}
        )
        
        # to_dict
        event_dict = event.to_dict()
        assert isinstance(event_dict["timestamp"], str)
        assert event_dict["event_type"] == "test_event"
        assert event_dict["data"] == {"message": "Hello"}
        
        # from_dict
        restored_event = BaseEvent.from_dict(event_dict)
        assert restored_event.event_id == event.event_id
        assert restored_event.user_id == event.user_id
        assert isinstance(restored_event.timestamp, datetime)


class TestConversationEvents:
    """Тесты событий диалога"""
    
    def test_user_message_event(self):
        """Тест события сообщения пользователя"""
        event = UserMessageEvent(
            user_id=12345,
            text="Привет, Химера!",
            emotion="curious",
            mode="chat"
        )
        
        assert event.event_type == "user_message"
        assert event.text == "Привет, Химера!"
        assert event.emotion == "curious"
        assert event.mode == "chat"
        
        # Проверка преобразования для MemoryActor
        memory_format = event.to_memory_format()
        assert memory_format["user_id"] == 12345
        assert memory_format["content"] == "Привет, Химера!"
        assert memory_format["emotion"] == "curious"
    
    def test_text_length_validation(self):
        """Тест валидации длины текста"""
        max_length = EVENT_CONFIG["event_types"]["user_message"]["max_text_length"]
        long_text = "x" * (max_length + 1)
        
        with pytest.raises(ValueError) as exc_info:
            event = UserMessageEvent(
                user_id=12345,
                text=long_text
            )
        assert "Text length" in str(exc_info.value)
    
    def test_bot_response_event(self):
        """Тест события ответа бота"""
        event = BotResponseEvent(
            user_id=12345,
            response_text="Здравствуй, человек!",
            generation_time_ms=150,
            mode_used="chat"
        )
        
        assert event.event_type == "bot_response"
        assert event.response_text == "Здравствуй, человек!"
        assert event.generation_time_ms == 150
        assert event.mode_used == "chat"
        
        # Проверка преобразования для MemoryActor
        memory_format = event.to_memory_format()
        assert memory_format["content"] == "Здравствуй, человек!"
        assert memory_format["mode"] == "chat"