import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from actors.base_actor import BaseActor
from actors.memory_actor import MemoryActor
from actors.message_types import create_memory_message
from services.deepseek_service import deepseek_service
from events.conversation_events import (
    UserMessageEvent, 
    BotResponseEvent, 
    ActorCoordinationEvent,
    SystemEvent
)
from events.event_store import EventStore
from config.coordination import COORDINATION_CONFIG
from config.settings import USE_JSON_MODE, DEFAULT_MODE

logger = logging.getLogger(__name__)


class UserSessionActor(BaseActor):
    """Координатор всех акторов в системе - управляет event-driven потоком"""
    
    def __init__(
        self, 
        memory_actor: MemoryActor,
        event_store: EventStore,
        config: Optional[Dict[str, Any]] = None
    ):
        # Используем конфиг координации если не передан кастомный
        if config is None:
            config = COORDINATION_CONFIG
            
        super().__init__("user_session", config)
        
        self.memory_actor = memory_actor
        self.event_store = event_store
        self.generation_service = deepseek_service
        
        # Параметры координации из конфига
        self.actor_timeout = config.get("actor_timeout_seconds", 30)
        self.retry_attempts = config.get("coordination_retry_attempts", 3)
        self.retry_delay_ms = config.get("coordination_retry_delay_ms", 500)
        
        # Метрики координации
        self._coordination_metrics = {
            "total_messages": 0,
            "successful_flows": 0,
            "failed_flows": 0,
            "actor_timeouts": 0,
            "avg_response_time": []
        }
    
    async def handle_message(self, message: Dict[str, Any]) -> Any:
        """Обработка входящих сообщений"""
        message_type = message.get("type")
        
        if message_type == "user_message":
            return await self.handle_user_message(
                message["text"],
                message["user_id"]
            )
        else:
            return {"error": f"Unknown message type: {message_type}"}
    
    async def handle_user_message(self, user_message: str, user_id: int) -> str:
        """
        Event-driven обработка сообщения пользователя
        
        Поток:
        1. UserMessageEvent создается
        2. Сохраняется в Event Store
        3. Сообщение сохраняется через MemoryActor
        4. Получаем контекст диалога
        5. Генерируем ответ
        6. BotResponseEvent создается
        7. Ответ сохраняется
        """
        start_time = time.time()
        self._coordination_metrics["total_messages"] += 1
        
        try:
            # 1. Создаем событие сообщения пользователя
            user_event = UserMessageEvent(
                user_id=user_id,
                text=user_message,
                timestamp=datetime.utcnow()
            )
            
            # 2. Сохраняем событие в Event Store
            await self.event_store.save_event(user_event)
            
            # 3. Сохраняем сообщение через MemoryActor
            await self._coordinate_actor_call(
                actor_name="memory",
                method=self.memory_actor.handle_message,
                message=create_memory_message(
                    "store_user_message",
                    user_event.to_memory_format()
                )
            )
            
            # 4. Получаем контекст диалога
            context_response = await self._coordinate_actor_call(
                actor_name="memory",
                method=self.memory_actor.handle_message,
                message=create_memory_message(
                    "get_conversation_context",
                    {"user_id": user_id, "limit": 10}
                )
            )
            
            # 5. Генерируем ответ
            generation_start = time.time()
            
            # Формируем контекст для генерации
            messages = context_response.get("messages", [])
            context_text = self._format_context_for_generation(messages)
            
            response_text = await self._coordinate_service_call(
                service_name="generation",
                method=self.generation_service.ask_deepseek,
                kwargs={
                    "message": user_message,
                    "user_id": user_id,
                    "use_json": USE_JSON_MODE,
                    "mode": DEFAULT_MODE
                }
            )
            
            generation_time_ms = int((time.time() - generation_start) * 1000)
            
            # 6. Создаем событие ответа бота
            bot_event = BotResponseEvent(
                user_id=user_id,
                response_text=response_text,
                generation_time_ms=generation_time_ms,
                mode_used=DEFAULT_MODE,
                timestamp=datetime.utcnow()
            )
            
            # 7. Сохраняем событие ответа
            await self.event_store.save_event(bot_event)
            
            # 8. Сохраняем ответ через MemoryActor
            await self._coordinate_actor_call(
                actor_name="memory",
                method=self.memory_actor.handle_message,
                message=create_memory_message(
                    "store_bot_response",
                    bot_event.to_memory_format()
                )
            )
            
            # Метрики успешного потока
            response_time = time.time() - start_time
            self._coordination_metrics["successful_flows"] += 1
            self._coordination_metrics["avg_response_time"].append(response_time)
            if len(self._coordination_metrics["avg_response_time"]) > 100:
                self._coordination_metrics["avg_response_time"].pop(0)
            
            # Логируем успешную координацию
            await self._log_coordination_event(
                "user_flow_complete",
                user_id,
                {
                    "response_time_seconds": response_time,
                    "generation_time_ms": generation_time_ms,
                    "context_messages": len(messages)
                }
            )
            
            return response_text
            
        except Exception as e:
            self._coordination_metrics["failed_flows"] += 1
            logger.error(f"Ошибка в event-driven потоке: {e}")
            
            # Логируем ошибку координации
            await self._log_coordination_event(
                "user_flow_error",
                user_id,
                {"error": str(e)},
                severity="error"
            )
            
            # Возвращаем fallback ответ
            return "Что-то пошло не так. Давайте попробуем еще раз?"
    
    async def _coordinate_actor_call(
        self, 
        actor_name: str, 
        method, 
        message: Any,
        timeout: Optional[float] = None
    ) -> Any:
        """Координация вызова актора с retry и timeout"""
        if timeout is None:
            timeout = self.actor_timeout
        
        retry_config = self.config["coordination_patterns"]["retry_patterns"].get(
            actor_name, 
            {"attempts": self.retry_attempts, "delay_ms": self.retry_delay_ms}
        )
        
        for attempt in range(retry_config["attempts"]):
            try:
                # Создаем событие координации
                coord_event = ActorCoordinationEvent(
                    source_actor="user_session",
                    target_actor=actor_name,
                    coordination_type="request",
                    user_id=getattr(message, 'data', {}).get('user_id')
                )
                
                start_time = time.time()
                
                # Вызов с timeout
                result = await asyncio.wait_for(
                    method(message),
                    timeout=timeout
                )
                
                # Успешная координация
                duration_ms = int((time.time() - start_time) * 1000)
                coord_event.coordination_type = "response"
                coord_event.duration_ms = duration_ms
                coord_event.success = True
                
                await self.event_store.save_event(coord_event)
                
                return result
                
            except asyncio.TimeoutError:
                self._coordination_metrics["actor_timeouts"] += 1
                logger.warning(f"Timeout при вызове {actor_name} (попытка {attempt + 1})")
                
                # Событие timeout
                coord_event.coordination_type = "timeout"
                coord_event.success = False
                coord_event.error_message = f"Timeout after {timeout}s"
                await self.event_store.save_event(coord_event)
                
                if attempt < retry_config["attempts"] - 1:
                    await asyncio.sleep(retry_config["delay_ms"] / 1000)
                else:
                    raise
                    
            except Exception as e:
                logger.error(f"Ошибка при вызове {actor_name}: {e}")
                
                # Событие ошибки
                coord_event.coordination_type = "error"
                coord_event.success = False
                coord_event.error_message = str(e)
                await self.event_store.save_event(coord_event)
                
                if attempt < retry_config["attempts"] - 1:
                    await asyncio.sleep(retry_config["delay_ms"] / 1000)
                else:
                    raise
    
    async def _coordinate_service_call(
        self,
        service_name: str,
        method,
        kwargs: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> Any:
        """Координация вызова сервиса"""
        if timeout is None:
            timeout = self.actor_timeout
        
        try:
            result = await asyncio.wait_for(
                method(**kwargs),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Timeout при вызове сервиса {service_name}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при вызове сервиса {service_name}: {e}")
            raise
    
    def _format_context_for_generation(self, messages: List[Dict[str, Any]]) -> str:
        """Форматирование контекста для генерации"""
        # Простое форматирование для текущего этапа
        # В будущем здесь будет более сложная логика
        context_parts = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            context_parts.append(f"{role}: {content}")
        
        return "\n".join(context_parts)
    
    async def _log_coordination_event(
        self, 
        event_subtype: str, 
        user_id: Optional[int],
        data: Dict[str, Any],
        severity: str = "info"
    ):
        """Логирование системных событий координации"""
        system_event = SystemEvent(
            event_subtype=event_subtype,
            user_id=user_id,
            data=data,
            severity=severity,
            actor_name="user_session"
        )
        await self.event_store.save_event(system_event)
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check с метриками координации"""
        base_health = await super().health_check()
        
        # Добавляем метрики координации
        avg_response_times = self._coordination_metrics["avg_response_time"]
        base_health.update({
            "coordination_metrics": {
                "total_messages": self._coordination_metrics["total_messages"],
                "successful_flows": self._coordination_metrics["successful_flows"],
                "failed_flows": self._coordination_metrics["failed_flows"],
                "actor_timeouts": self._coordination_metrics["actor_timeouts"],
                "avg_response_time": sum(avg_response_times) / len(avg_response_times) if avg_response_times else 0,
                "success_rate": (
                    self._coordination_metrics["successful_flows"] / 
                    self._coordination_metrics["total_messages"]
                ) if self._coordination_metrics["total_messages"] > 0 else 0
            }
        })
        
        return base_health