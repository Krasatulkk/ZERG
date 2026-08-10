import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from dotenv import load_dotenv

# ---------- Настройка логирования ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Загрузка переменных ----------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Токен основного бота не найден в переменных окружения")

# ---------- Адрес Cloudflare Worker ----------
BOT_API_BASE_URL = "https://round-hill-9d0b.fedorbolgarov2.workers.dev"

# ---------- Создание бота ----------
bot = Bot(token=BOT_TOKEN, base_url=BOT_API_BASE_URL)
dp = Dispatcher()

# ---------- Клавиатура с кнопкой Mini App ----------
webapp_btn = KeyboardButton(
    text="📱 Открыть приложение",
    web_app=WebAppInfo(url="https://Krasatulkk.github.io/ZERG/")
)
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [webapp_btn],
        [KeyboardButton(text="ℹ️ Помощь"), KeyboardButton(text="📖 О боте")]
    ],
    resize_keyboard=True
)

# ---------- Обработчики команд ----------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Приветствую! Gehenna bot работает через Cloudflare Worker.\n"
        "Теперь мне не страшны блокировки!",
        reply_markup=main_kb
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📖 Доступные команды:\n"
        "/start — приветствие\n"
        "/about — о возможностях Gehenna AI\n"
        "/capabilities — то же, что /about\n"
        "/reset — сброс диалога (заглушка)"
    )

@dp.message(Command("about"))
async def cmd_about(message: types.Message):
    await message.answer(
        "Возможности Gehenna AI безграничны! "
        "ZERG создали лучший ИИ."
    )

@dp.message(Command("capabilities"))
async def cmd_capabilities(message: types.Message):
    await message.answer(
        "Возможности Gehenna AI безграничны! "
        "ZERG создали лучший ИИ."
    )

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    await message.answer("🔄 Сброс выполнен.")

# ---------- Универсальный обработчик всех остальных сообщений ----------
@dp.message()
async def handle_message(message: types.Message):
    # 1. Данные из Mini App
    if message.web_app_data:
        await message.answer(f"📩 Данные из Mini App: {message.web_app_data.data}")
        return

    # 2. Обычные текстовые сообщения или неизвестные команды
    if message.text:
        if message.text.startswith("/"):
            await message.answer(
                "🔧 СЕЙЧАС ПРОВОДЯТСЯ ТЕХНИЧЕСКИЕ РАБОТЫ,\n"
                "приносим свои извинения."
            )
        else:
            user_text = message.text
            await message.answer(
                f"❓ Вы задали вопрос: «{user_text}»\n\n"
                "🔧 СЕЙЧАС ПРОВОДЯТСЯ ТЕХНИЧЕСКИЕ РАБОТЫ,\n"
                "приносим свои извинения."
            )

# ---------- Основная функция ----------
async def main():
    logger.info("🤖 Бот запущен через Cloudflare Worker!")
    await dp.start_polling(bot)

# ---------- Точка входа ----------
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise
