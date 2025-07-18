# Конфигурация для MemoryActor
MEMORY_CONFIG = {
    "stm_limit": 25,                    # Кольцевой буфер лимит
    "cleanup_batch_size": 10,           # Размер batch для cleanup
    "query_timeout_seconds": 30,        # Timeout для DB запросов
    "retry_attempts": 3,                # Попытки retry при ошибках
    "retry_delay_seconds": 1,           # Задержка между retry
    "context_max_length": 5000,         # Максимальная длина контекста
    "importance_threshold": 5,          # Порог важности для LTM готовности
    "performance_log_enabled": True     # Логирование производительности
}

# Добавьте этот блок в конец файла config/memory.py

# Event-related настройки для MemoryActor
MEMORY_EVENT_CONFIG = {
    "auto_event_generation": True,          # Автогенерация событий
    "event_context_max_items": 50,          # Максимум событий в контексте
    "event_filtering_enabled": True,        # Фильтрация событий по типу
    "memory_event_batch_size": 20,          # Batch size для memory событий
    "event_storage_enabled": True,          # Сохранять события в БД
    "event_deduplication": True,            # Дедупликация событий
    "event_ttl_seconds": 86400             # TTL для временных событий (24 часа)
}