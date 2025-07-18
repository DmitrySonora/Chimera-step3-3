# Настройки координации акторов

COORDINATION_CONFIG = {
    "actor_timeout_seconds": 30,            # Timeout межакторных вызовов
    "coordination_retry_attempts": 3,       # Попытки retry при ошибках
    "coordination_retry_delay_ms": 500,     # Задержка между retry
    "max_concurrent_actors": 10,            # Максимум одновременных акторов
    "coordination_log_level": "INFO",       # Уровень логирования координации
    "event_propagation_timeout": 10,        # Timeout распространения событий
    "graceful_shutdown_timeout": 60,        # Timeout graceful shutdown
    "health_check_interval_seconds": 120,   # Интервал health check координации
    
    # Паттерны координации
    "coordination_patterns": {
        "sequential_actors": ["memory", "generation"],    # Последовательные вызовы
        "parallel_actors": [],                           # Параллельные вызовы (пока нет)
        "retry_patterns": {                              # Retry стратегии
            "memory": {"attempts": 3, "delay_ms": 500},
            "generation": {"attempts": 2, "delay_ms": 1000}
        }
    },
    
    # Метрики координации
    "metrics": {
        "enabled": True,
        "buffer_size": 1000,
        "flush_interval_seconds": 60
    }
}