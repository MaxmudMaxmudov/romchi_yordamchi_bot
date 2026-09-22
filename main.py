import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeDefault,
    MenuButtonCommands,
)

from config import BOT_TOKEN
import database as db
from scheduler import setup_scheduler
from handlers import tracking, admin_flow

logging.basicConfig(level=logging.INFO)

# Shaxsiy chatda "/" bosilganda chiqadigan menyu
BOT_COMMANDS = [
    BotCommand(command="new_reminder", description="🆕 Yangi eslatma yaratish"),
    BotCommand(command="list_reminders", description="📋 Eslatmalar ro'yxati va holati"),
    BotCommand(command="show_text", description="📝 Eslatma matnlari: /show_text <id>"),
    BotCommand(command="stop", description="⏹ Shu oylik eslatmani to'xtatish: /stop <id>"),
    BotCommand(command="pause", description="⏸ Butunlay to'xtatish: /pause <id>"),
    BotCommand(command="resume", description="▶️ Qayta yoqish: /resume <id>"),
    BotCommand(command="delete_reminder", description="🗑 O'chirish: /delete_reminder <id>"),
    BotCommand(command="cancel", description="✖️ Joriy oqimni bekor qilish"),
    BotCommand(command="help", description="❓ Yordam"),
]


async def setup_bot_commands(bot: Bot):
    """
    Buyruqlar menyusini Telegram'ga yozib qo'yamiz — shundan keyin shaxsiy
    chatda input maydoniga "/" yozilsa, ro'yxat o'zi ochiladi.

    Ro'yxat ikki joyga yoziladi: `all_private_chats` (asosiysi) va `default`
    (ba'zi mijozlar shu yerdan o'qiydi). Guruhlarda ataylab bo'sh qoldiramiz.
    """
    await bot.set_my_commands(BOT_COMMANDS, scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(BOT_COMMANDS, scope=BotCommandScopeDefault())
    await bot.set_my_commands([], scope=BotCommandScopeAllGroupChats())
    # Input yonidagi tugma "Menu" bo'lib, bosilganda shu ro'yxatni ochsin
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())


async def main():
    await db.init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())

    # Tartib muhim: avval admin oqimi (DM), keyin guruh kuzatuvi
    dp.include_router(admin_flow.router)
    dp.include_router(tracking.router)

    setup_scheduler(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    await setup_bot_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
