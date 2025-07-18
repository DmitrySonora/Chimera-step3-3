import pytest
from utils.json_utils import extract_json_from_text, safe_json_parse, validate_json_response


def test_extract_clean_json():
    """Тест извлечения чистого JSON"""
    text = '{"response": "Привет!"}'
    result = extract_json_from_text(text)
    assert result == {"response": "Привет!"}


def test_extract_json_with_text():
    """Тест извлечения JSON из текста"""
    text = 'Вот ответ: {"response": "Привет!"} конец'
    result = extract_json_from_text(text)
    assert result == {"response": "Привет!"}


def test_safe_json_parse_with_default():
    """Тест безопасного парсинга с default значением"""
    text = "Это не JSON"
    default = {"response": "default"}
    result = safe_json_parse(text, default)
    assert result == default


def test_validate_json_response():
    """Тест валидации JSON ответа"""
    valid = {"response": "текст"}
    invalid1 = {"data": "текст"}
    invalid2 = {"response": 123}
    
    assert validate_json_response(valid) == True
    assert validate_json_response(invalid1) == False
    assert validate_json_response(invalid2) == False