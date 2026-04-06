import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats

from config import settings
from db import async_session
from handlers.admin import router as admin_router
from handlers.user import router as user_router
from middlewares.admin_filter import AdminFilterMiddleware
from middlewares.session_middleware import SessionMiddleware
from services.reminders import ReminderService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ── Bot commands setup ──────────────────────────────────────────────────────

USER_COMMANDS = [
    BotCommand(command="start", description="Запустить бота"),
    BotCommand(command="my", description="Мои записи"),
    BotCommand(command="reminders", description="Напоминания"),
    BotCommand(command="trainings", description="Предстоящие мастерки"),
]


async def set_bot_commands(bot: Bot) -> None:
    """Set commands for all private chats."""
    await bot.set_my_commands(
        USER_COMMANDS, scope=BotCommandScopeAllPrivateChats()
    )


# ── Entry point ──────────────────────────────────────────────────────────────

async def main() -> None:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register middlewares on dispatcher level (applies to all routers)
    dp.message.middleware(SessionMiddleware(async_session))
    dp.callback_query.middleware(SessionMiddleware(async_session))

    # Register admin filter on admin router
    admin_router.message.middleware(AdminFilterMiddleware())
    admin_router.callback_query.middleware(AdminFilterMiddleware())

    # Include routers
    # Admin router first so admin commands take priority
    dp.include_router(admin_router)
    dp.include_router(user_router)

    # Set commands
    await set_bot_commands(bot)

    # Start reminder service
    reminder_service = ReminderService(
        bot=bot,
        session_factory=async_session,
        reminder_hours=settings.REMINDER_HOURS,
    )
    reminder_service.start()

    logger.info("Starting polling...")
    try:
        await dp.start_polling(bot)
    finally:
        reminder_service.stop()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
