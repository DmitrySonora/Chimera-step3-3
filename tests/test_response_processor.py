import pytest
import asyncio
from services.response_processor import ResponseProcessor


@pytest.mark.asyncio
async def test_clean_bot_response():
    """Тест очистки ответа"""
    processor = ResponseProcessor()
    
    # Тест удаления избыточного форматирования
    text = "***Привет!*** ___Как дела?___\n\n\n\nХорошо!"
    cleaned = processor.clean_bot_response(text)
    assert cleaned == "**Привет!** __Как дела?__\n\nХорошо!"


@pytest.mark.asyncio
async def test_detect_format_violations():
    """Тест детекции нарушений формата"""
    processor = ResponseProcessor()
    
    # Тест различных нарушений
    violations1 = processor.detect_format_violations("Извините, извините, извините!")
    assert "excessive_apology" in violations1
    
    violations2 = processor.detect_format_violations("Я являюсь ИИ ассистентом")
    assert "ai_disclosure" in violations2
    
    violations3 = processor.detect_format_violations("😀😀😀😀😀😀")
    assert "excessive_emoji" in violations3


@pytest.mark.asyncio
async def test_process_json_response():
    """Тест обработки JSON ответа"""
    processor = ResponseProcessor()
    
    json_response = '{"response": "Привет, я Химера!"}'
    result = await processor.process_response(json_response, use_json=True)
    assert result == "Привет, я Химера!"
    
    # Тест с невалидным JSON
    invalid_json = "Это не JSON ответ"
    result2 = await processor.process_response(invalid_json, use_json=True)
    assert result2 == invalid_json  # Должен вернуть как есть