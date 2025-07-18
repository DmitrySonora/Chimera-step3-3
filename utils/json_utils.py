import json
import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Извлекает JSON из текста, даже если он окружен другим текстом
    
    Args:
        text: Текст, возможно содержащий JSON
        
    Returns:
        Распарсенный JSON или None
    """
    try:
        # Сначала пробуем распарсить как чистый JSON
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Ищем JSON-подобные структуры в тексте
    json_patterns = [
        r'\{[^{}]*\}',  # Простой одноуровневый JSON
        r'\{.*?\}',     # JSON с жадным поиском
        r'\{[\s\S]*\}', # JSON с переносами строк
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
    
    return None


def safe_json_parse(text: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Безопасный парсинг JSON с fallback значением
    
    Args:
        text: Текст для парсинга
        default: Значение по умолчанию при ошибке
        
    Returns:
        Распарсенный JSON или default
    """
    if default is None:
        default = {}
    
    try:
        # Пробуем извлечь JSON из текста
        result = extract_json_from_text(text)
        if result is not None:
            return result
            
        # Если не получилось, возвращаем default
        logger.warning(f"Failed to parse JSON from text: {text[:100]}...")
        return default
        
    except Exception as e:
        logger.error(f"Error in safe_json_parse: {e}")
        return default


def validate_json_response(data: Dict[str, Any]) -> bool:
    """
    Проверяет, что JSON ответ содержит обязательное поле 'response'
    
    Args:
        data: Распарсенный JSON
        
    Returns:
        True если валидный, False если нет
    """
    return isinstance(data, dict) and "response" in data and isinstance(data["response"], str)