# Общие настройки для всех акторов
ACTOR_CONFIG = {
    "message_timeout_seconds": 10,      # Timeout межакторных сообщений
    "health_check_interval": 300,       # Интервал health check (5 мин)
    "max_queue_size": 1000,            # Максимальный размер очереди сообщений
    "graceful_shutdown_timeout": 30,    # Timeout graceful shutdown
    "performance_metrics_enabled": True # Метрики производительности
}