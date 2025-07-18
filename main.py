import asyncio
import logging
import signal
import sys
from telegram_bot import telegram_bot

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Отключить лишнюю болтовню от httpx
logging.getLogger("httpx").setLevel(logging.WARNING)


async def main():
    """Главная функция запуска системы"""
    logger.info("🐲 Химера Великолепнейшая уже здесь 🐲")
    
    try:
        # Запускаем бота
        await telegram_bot.run()
        
        # Держим бота работающим
        while telegram_bot.is_running:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        await telegram_bot.shutdown()
        logger.info("🐲 Химера Великолепнейшая покинула вас 🐲")


def signal_handler(sig, frame):
    """Обработчик сигнала завершения"""
    logger.info("🐲 Получен сигнал завершения")
    asyncio.create_task(telegram_bot.shutdown())
    sys.exit(0)


if __name__ == "__main__":
    # Регистрируем обработчик сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запускаем асинхронный main
    asyncio.run(main())