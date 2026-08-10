import asyncio
import os
import logging
import aiohttp
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

# ---------- Токен бота-уведомителя и ваш Chat ID (вшиты напрямую) ----------
NOTIFIER_BOT_TOKEN = "8608610389:AAFVbkU58G7Mu6XAdo9Z-mBh_ZYqa_CaTSU"
YOUR_CHAT_ID = "5609029269"

# ---------- Функция отправки уведомления ----------
async def send_error_notification(error_text: str):
    """Отправляет сообщение об ошибке вам в Telegram через бота-уведомителя"""
    url = f"https://api.telegram.org/bot{NOTIFIER_BOT_TOKEN}/sendMessage"
    message = f"🚨 *БОТ УПАЛ!*\n\n```\n{error_text[:3000]}\n```"
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(url, json={
                "chat_id": YOUR_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            })
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление: {e}")

# ---------- Адрес Cloudflare Worker (ваш прокси) ----------
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
        "👋 Привет! Бот работает через Cloudflare Worker.\n"
        "Теперь мне не страшны блокировки!",
        reply_markup=main_kb
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("📖 /start, /about, /reset")

@dp.message(Command("about"))
async def cmd_about(message: types.Message):
    await message.answer("🤖 Бот на aiogram + Cloudflare Worker.")

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    await message.answer("🔄 Сброс выполнен.")

@dp.message()
async def handle_message(message: types.Message):
    if message.web_app_data:
        await message.answer(f"📩 Данные из Mini App: {message.web_app_data.data}")
    elif message.text and not message.text.startswith("/"):
        await message.answer(f"Вы написали: {message.text}")

# ---------- Основная функция ----------
async def main():
    logger.info("🤖 Бот запущен через Cloudflare Worker!")
    await dp.start_polling(bot)

# ---------- Точка входа с перехватом ошибок ----------
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        error_text = str(e)
        logger.error(f"Критическая ошибка: {error_text}")
        asyncio.run(send_error_notification(error_text))
        raise
