# Конфигурация Event Sourcing для Химеры 2.0

EVENT_CONFIG = {
    "max_event_size_bytes": 64000,          # Максимальный размер события
    "event_batch_size": 100,                # Размер batch для записи событий
    "event_retention_days": 365,            # Время хранения событий
    "event_compression_enabled": True,      # Сжатие больших событий
    "event_validation_enabled": True,       # Валидация структуры событий
    "event_metadata_max_size": 1024,        # Максимальный размер метаданных
    "stream_id_format": "user_{user_id}",   # Формат stream ID
    "event_timestamp_precision": "milliseconds",  # Точность timestamp
    
    # Типы событий и их настройки
    "event_types": {
        "user_message": {
            "max_text_length": 4096,
            "required_fields": ["text", "user_id"],
            "optional_fields": ["emotion", "mode"]
        },
        "bot_response": {
            "max_text_length": 8192,
            "required_fields": ["response_text", "user_id", "generation_time_ms"],
            "optional_fields": ["mode_used", "injection_used"]
        },
        "system_event": {
            "required_fields": ["event_subtype", "data"],
            "optional_fields": ["severity", "actor_name"]
        }
    }
}