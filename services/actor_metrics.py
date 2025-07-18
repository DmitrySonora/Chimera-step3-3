import time
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class ActorMetrics:
    """Сбор метрик производительности для акторов"""
    
    def __init__(self, actor_name: str):
        self.actor_name = actor_name
        self.metrics = {
            "operations": {},
            "errors": {},
            "latencies": {}
        }
    
    def record_operation(self, operation: str, duration: float, success: bool = True):
        """Записать метрику операции"""
        if operation not in self.metrics["operations"]:
            self.metrics["operations"][operation] = {
                "count": 0,
                "success": 0,
                "failed": 0,
                "total_duration": 0
            }
        
        self.metrics["operations"][operation]["count"] += 1
        self.metrics["operations"][operation]["total_duration"] += duration
        
        if success:
            self.metrics["operations"][operation]["success"] += 1
        else:
            self.metrics["operations"][operation]["failed"] += 1
    
    def record_error(self, operation: str, error: Exception):
        """Записать ошибку"""
        error_type = type(error).__name__
        
        if operation not in self.metrics["errors"]:
            self.metrics["errors"][operation] = {}
        
        if error_type not in self.metrics["errors"][operation]:
            self.metrics["errors"][operation][error_type] = 0
        
        self.metrics["errors"][operation][error_type] += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Получить сводку метрик"""
        summary = {
            "actor": self.actor_name,
            "timestamp": datetime.utcnow().isoformat(),
            "operations": {}
        }
        
        for op, stats in self.metrics["operations"].items():
            if stats["count"] > 0:
                summary["operations"][op] = {
                    "count": stats["count"],
                    "success_rate": stats["success"] / stats["count"],
                    "avg_duration": stats["total_duration"] / stats["count"],
                    "errors": self.metrics["errors"].get(op, {})
                }
        
        return summary


def measure_performance(operation_name: str):
    """Декоратор для измерения производительности асинхронных методов"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            start_time = time.time()
            success = True
            
            try:
                result = await func(self, *args, **kwargs)
                return result
            except Exception as e:
                success = False
                if hasattr(self, 'metrics') and isinstance(self.metrics, ActorMetrics):
                    self.metrics.record_error(operation_name, e)
                raise
            finally:
                duration = time.time() - start_time
                if hasattr(self, 'metrics') and isinstance(self.metrics, ActorMetrics):
                    self.metrics.record_operation(operation_name, duration, success)
                
                # Логируем если включено
                if hasattr(self, 'config') and self.config.get('performance_log_enabled'):
                    self.logger.debug(
                        f"Operation '{operation_name}' took {duration:.3f}s "
                        f"(success={success})"
                    )
        
        return wrapper
    return decorator