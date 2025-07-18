import logging
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction
from config.settings import TELEGRAM_BOT_TOKEN, TYPING_DELAY, USER_MESSAGES, USE_JSON_MODE, DEFAULT_MODE
from services.deepseek_service import deepseek_service
from events.event_store import EventStore
from actors.memory_actor import MemoryActor
from actors.user_session_actor import UserSessionActor
from actors.message_types import create_memory_message
from database.connection import db

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class ChimeraTelegramBot:
    """Telegram бот Химеры с Event-driven архитектурой"""
    
    def __init__(self):
        self.application = None
        self.is_running = False
        self.memory_actor = None
        self.event_store = None
        self.user_session_actor = None
        self.is_typing = False
    
    async def send_typing_action(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
        """Отправка индикатора печати"""
        while self.is_typing:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await asyncio.sleep(TYPING_DELAY)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработка входящих сообщений через UserSessionActor
        """
        try:
            # Извлекаем данные пользователя
            user_id = update.message.from_user.id
            username = update.message.from_user.username or "unknown"
            message_text = update.message.text
            chat_id = update.effective_chat.id
            
            logger.info(f"📨 Сообщение от {username} (ID: {user_id}): {message_text[:50]}...")
            
            # Запускаем индикатор печати
            self.is_typing = True
            typing_task = asyncio.create_task(
                self.send_typing_action(context, chat_id)
            )
            
            try:
                # Передаем обработку в UserSessionActor (event-driven поток)
                response = await self.user_session_actor.handle_user_message(
                    user_message=message_text,
                    user_id=user_id
                )
                
                # Останавливаем индикатор печати
                self.is_typing = False
                await typing_task
                
                # Отправляем ответ
                await update.message.reply_text(response)
                
                logger.info(f"✅ Ответ отправлен пользователю {user_id}")
                
            except Exception as e:
                self.is_typing = False
                logger.error(f"Error in message processing: {e}")
                await update.message.reply_text(USER_MESSAGES["error_processing"])
                
        except Exception as e:
            logger.error(f"Critical error in handle_message: {e}")
            if update and update.message:
                await update.message.reply_text(USER_MESSAGES["critical_error"])
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработка команды /start"""
        user_id = update.message.from_user.id
        username = update.message.from_user.username or "unknown"
        
        logger.info(f"🚀 Команда /start от {username} (ID: {user_id})")
        
        # Можно сохранить событие старта через UserSessionActor
        # Но для простоты пока просто отправляем приветствие
        await update.message.reply_text(USER_MESSAGES["welcome"])
    
    async def initialize(self):
        """Инициализация бота и всех компонентов"""
        logger.info("🐲 Инициализация Химеры...")
        
        # Инициализируем базу данных
        await db.initialize()
        
        # Создаем Event Store
        self.event_store = EventStore(db)
        await self.event_store.initialize()
        logger.info("🗄️ Event Store инициализирован")
        
        # Создаем и инициализируем MemoryActor
        self.memory_actor = MemoryActor(db)
        await self.memory_actor.initialize()
        logger.info("🧠 MemoryActor инициализирован")
        
        # Создаем UserSessionActor - центральный координатор
        self.user_session_actor = UserSessionActor(
            memory_actor=self.memory_actor,
            event_store=self.event_store
        )
        await self.user_session_actor.initialize()
        logger.info("🎭 UserSessionActor инициализирован")
        
        # Инициализируем Telegram приложение
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Регистрация обработчиков
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        
        self.is_running = True
        logger.info("🐲 Химера проснулась и готова к общению!")
    
    async def run(self):
        """Запуск бота"""
        await self.initialize()
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("🐲 Химера слушает...")
    
    async def shutdown(self):
        """Остановка бота и всех компонентов"""
        logger.info("🐲 Начинаем остановку Химеры...")
        
        # Останавливаем UserSessionActor
        if self.user_session_actor:
            await self.user_session_actor.shutdown()
            logger.info("🎭 UserSessionActor остановлен")
        
        # Останавливаем MemoryActor
        if self.memory_actor:
            await self.memory_actor.shutdown()
            logger.info("🧠 MemoryActor остановлен")
        
        # Останавливаем Event Store
        if self.event_store:
            await self.event_store.shutdown()
            logger.info("🗄️ Event Store остановлен")
        
        # Закрываем соединение с БД
        await db.close()
        
        # Останавливаем Telegram приложение
        if self.application:
            await self.application.stop()
            
        self.is_running = False
        logger.info("🐲 Химера заснула. До новых встреч!")


# Глобальный экземпляр бота
telegram_bot = ChimeraTelegramBot()