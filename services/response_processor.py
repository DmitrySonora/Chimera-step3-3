import re
import logging
from typing import Dict, Any, List, Optional, Callable
from utils.json_utils import safe_json_parse, validate_json_response

logger = logging.getLogger(__name__)


class ResponseProcessor:
    """Модульный обработчик ответов - готов к pipeline архитектуре"""
    
    def __init__(self):
        self.processors: List[Callable] = []  # Готовность к pipeline (этап 8)
        self.format_violations = []  # Статистика нарушений
    
    async def process_response(self, response: str, mode: str = "auto", use_json: bool = False) -> str:
        """
        Обрабатывает ответ от модели
        
        Args:
            response: Сырой ответ от модели
            mode: Режим обработки (для будущих этапов)
            use_json: Ожидается ли JSON формат
            
        Returns:
            Обработанный текст ответа
        """
        # Если ожидаем JSON, пробуем распарсить
        if use_json:
            json_data = safe_json_parse(response)
            if validate_json_response(json_data):
                response = json_data["response"]
            else:
                logger.warning("Invalid JSON response format, using raw text")
        
        # Применяем очистку
        cleaned = self.clean_bot_response(response)
        
        # Детектируем нарушения формата
        violations = self.detect_format_violations(cleaned)
        if violations:
            self.format_violations.extend(violations)
            logger.info(f"Format violations detected: {violations}")
        
        # Готовность к pipeline обработчикам (этап 8)
        result = cleaned
        for processor in self.processors:
            result = await processor(result, mode)
        
        return result
    
    def clean_bot_response(self, text: str) -> str:
        """
        Очищает ответ от нежелательного форматирования
        
        Args:
            text: Сырой текст ответа
            
        Returns:
            Очищенный текст
        """
        # Удаляем избыточные markdown символы
        patterns_to_clean = [
            (r'\*{3,}', '**'),  # Тройные и более звездочки -> двойные
            (r'_{3,}', '__'),   # Тройные и более подчеркивания -> двойные
            (r'\n{3,}', '\n\n'), # Тройные и более переносы -> двойные
            (r'^#+\s*', ''),    # Заголовки в начале строки
            (r'\[([^\]]+)\]\([^\)]+\)', r'\1'),  # Markdown ссылки -> текст
        ]
        
        cleaned = text
        for pattern, replacement in patterns_to_clean:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.MULTILINE)
        
        # Убираем пробелы в начале и конце
        cleaned = cleaned.strip()
        
        return cleaned
    
    def detect_format_violations(self, text: str) -> List[str]:
        """
        Детектирует нарушения характера Химеры
        
        Args:
            text: Текст для проверки
            
        Returns:
            Список обнаруженных нарушений
        """
        violations = []
        
        # Паттерны нарушений
        violation_patterns = {
            "excessive_apology": r'(извините|простите|извиняюсь|прошу прощения|sorry|apolog(?:y|ies|ize))',
            "ai_disclosure": r'(я\s+(?:являюсь|есть)\s+(?:ии|ai|искусственн))',
            "excessive_emoji": r'([😀-🙏🌀-🗿]{3,})',
            "code_blocks": r'```[\s\S]*?```',
            "numbered_lists": r'^\d+\.\s+',
            "bullet_points": r'^[\*\-•]\s+',
        }
        
        for violation_type, pattern in violation_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            if violation_type == "excessive_apology":
                if len(matches) > 1:
                    violations.append(violation_type)
            else:
                if matches:
                    violations.append(violation_type)
        
        return violations
    
    async def fallback_to_normal(self, original_response: str) -> str:
        """
        Fallback механизм при ошибках JSON обработки
        
        Args:
            original_response: Оригинальный ответ
            
        Returns:
            Обработанный ответ в обычном режиме
        """
        logger.info("Falling back to normal response processing")
        return await self.process_response(original_response, use_json=False)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику обработки (для будущей аналитики)"""
        violation_counts = {}
        for violation in self.format_violations:
            violation_counts[violation] = violation_counts.get(violation, 0) + 1
        
        return {
            "total_violations": len(self.format_violations),
            "violation_types": violation_counts
        }


# Глобальный экземпляр процессора
response_processor = ResponseProcessor()