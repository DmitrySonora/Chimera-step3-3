import os
from dotenv import load_dotenv

load_dotenv()

# Telegram настройки
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# DeepSeek API настройки
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# Логирование
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Таймауты
API_TIMEOUT = 30  # секунд
TYPING_DELAY = 0.5  # секунд между обновлениями typing

# Режимы работы
USE_JSON_MODE = True  # Использовать JSON режим для ответов (True/False)
DEFAULT_MODE = "default"  # Режим по умолчанию (default/expert/creative/empathetic)

# Лимиты сообщений
DAILY_MESSAGE_LIMIT = 10  # Дневной лимит сообщений для демо-доступа

# Пользовательские сообщения
USER_MESSAGES = {
    "welcome": (
        f"Привет! Я — Химера, искусственный интеллект магического реализма!\n\n"
        f"✷ Это демо-доступ на {DAILY_MESSAGE_LIMIT} сообщений в день\n"
        f"✷ Когда лимит закончится, введите 🔑 пароль от подписки и общайтесь безлимитно\n"
        f"✷ Подписка и мануал здесь ☞ @aihimera\n\n"
        f"✨Теперь можете общаться — Химера ждёт!✨"
    ),
    
    "error_processing": (
        "Что-то случилось. Где-то я поломалась. Попробуйте еще раз"
    ),
    
    "service_unavailable": (
        "Что-то мне нехорошо. Извините, но мне сейчас не до вас"
    ),
    
    "critical_error": (
        "Что-то случилось. Где-то я поломалась"
    )
}