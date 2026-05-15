import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot import config, database
from bot.handlers import user, admin, faq, broadcast
from bot.middlewares.claim_guard import ClaimGuardMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

async def main():
    if not config.BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан в .env!")
    if not config.GROUP_ID:
        raise ValueError("GROUP_ID не задан в .env!")

    # Init DB
    await database.init_db()
    logger.info("База данных инициализирована.")

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())

    # Register claim guard middleware (only for group messages)
    dp.message.middleware(ClaimGuardMiddleware())

    # Register routers (order matters!)
    dp.include_router(broadcast.router)  # Broadcast FSM (before user catch-all)
    dp.include_router(faq.router)        # FAQ handlers
    dp.include_router(admin.router)      # Admin commands in group
    dp.include_router(user.router)       # User private messages (catch-all last)

    logger.info("Бот запускается...")

    # Set bot commands for users
    from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeAllGroupChats
    await bot.set_my_commands(
        commands=[
            BotCommand(command="start", description="Запустить бота"),
            BotCommand(command="faq", description="Часто задаваемые вопросы"),
        ],
        scope=BotCommandScopeDefault(),
    )
    # Group commands for admins
    await bot.set_my_commands(
        commands=[
            BotCommand(command="claim", description="Заклеймить тикет"),
            BotCommand(command="unclaim", description="Снять клейм"),
            BotCommand(command="add", description="Добавить модера в тикет"),
            BotCommand(command="close", description="Закрыть тикет"),
            BotCommand(command="info", description="Инфо о тикете"),
            BotCommand(command="silent", description="Вкл/выкл тихий режим"),
        ],
        scope=BotCommandScopeAllGroupChats(),
    )

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("Бот остановлен.")

if __name__ == "__main__":
    asyncio.run(main())