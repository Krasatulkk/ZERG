import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Токен не найден в .env")

# ---- Адрес Worker (без слеша в конце) ----
BOT_API_BASE_URL = "https://round-hill-9d0b.fedorbolgarov2.workers.dev"

# ---- Создаём бота с кастомным base_url ----
# aiogram будет автоматически добавлять токен и метод, формируя /<TOKEN>/<METHOD>
bot = Bot(token=BOT_TOKEN, base_url=BOT_API_BASE_URL)

dp = Dispatcher()

# ---- Клавиатура с кнопкой Mini App (замените ссылку позже) ----
webapp_btn = KeyboardButton(
    text="📱 Открыть приложение",
    web_app=WebAppInfo(url="https://ваш-сайт/index.html")  # замените позже
)
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [webapp_btn],
        [KeyboardButton(text="ℹ️ Помощь"), KeyboardButton(text="📖 О боте")]
    ],
    resize_keyboard=True
)

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

async def main():
    logger.info("🤖 Бот запущен через Cloudflare Worker!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
