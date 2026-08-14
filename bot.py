import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
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

# ---------- Хранилище состояний и бот ----------
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN, base_url=BOT_API_BASE_URL)
dp = Dispatcher(storage=storage)

# ===================== FSM ДЛЯ FEEDBACK =====================
class FeedbackStates(StatesGroup):
    waiting_for_feedback = State()  # ожидаем текст отзыва

# Хранилище отзывов (в памяти, для заглушки)
feedbacks = []

# ===================== ОБРАБОТЧИК ОШИБОК =====================
@dp.errors()
async def handle_errors(update: types.Update, exception: Exception) -> bool:
    logger.error(f"Произошла ошибка: {exception}", exc_info=True)
    chat_id = None
    if update.message:
        chat_id = update.message.chat.id
    elif update.callback_query:
        chat_id = update.callback_query.message.chat.id
    elif update.inline_query:
        return True
    if chat_id:
        try:
            await bot.send_message(chat_id, "🔧 СЕЙЧАС ПРОВОДЯТСЯ ТЕХНИЧЕСКИЕ РАБОТЫ,\nприносим свои извинения.")
        except Exception:
            pass
    return True

# ===================== КЛАВИАТУРА =====================
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

# ---------- Глобальный список для /reset (удаление сообщений) ----------
bot_messages = []

async def send_and_store(chat_id: int, text: str, **kwargs):
    sent = await bot.send_message(chat_id, text, **kwargs)
    bot_messages.append(sent.message_id)
    if len(bot_messages) > 100:
        bot_messages.pop(0)
    return sent

# ===================== ОБРАБОТЧИКИ КОМАНД =====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Вас приветствует Gehenna AI 👋,\nАнализирую, предсказываю, созидаю.",
        reply_markup=main_kb
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📖 Доступные команды:\n"
        "/start — приветствие\n"
        "/about — о возможностях Gehenna AI\n"
        "/capabilities — то же, что /about\n"
        "/feedback — оставить отзыв или пожелание\n"
        "/reset — сбросить диалог и очистить чат (удалить мои сообщения)"
    )

@dp.message(Command("about"))
async def cmd_about(message: types.Message):
    await message.answer(
        "Возможности Gehenna AI безграничны! ZERG создали лучший ИИ."
    )

@dp.message(Command("capabilities"))
async def cmd_capabilities(message: types.Message):
    await message.answer(
        "Возможности Gehenna AI безграничны! ZERG создали лучший ИИ."
    )

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message, state: FSMContext):
    await state.clear()
    deleted = 0
    to_delete = bot_messages[-10:]
    for msg_id in reversed(to_delete):
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
            deleted += 1
        except Exception:
            pass
    bot_messages.clear()
    await message.answer(
        f"🔄 Диалог сброшен. Удалено {deleted} моих сообщений.\nНачинаем заново!",
        reply_markup=main_kb
    )

# ---------- Обработчик команды /feedback ----------
@dp.message(Command("feedback"))
async def cmd_feedback(message: types.Message, state: FSMContext):
    await state.set_state(FeedbackStates.waiting_for_feedback)
    await message.answer(
        "📝 Напишите ваш отзыв или пожелание. Мы очень ценим ваше мнение!"
    )

@dp.message(StateFilter(FeedbackStates.waiting_for_feedback))
async def process_feedback(message: types.Message, state: FSMContext):
    user_text = message.text
    if not user_text:
        await message.answer("Пожалуйста, напишите текст отзыва.")
        return
    # Сохраняем отзыв (заглушка – в список)
    feedbacks.append({
        "user_id": message.from_user.id,
        "username": message.from_user.username or "без_имени",
        "text": user_text,
        "date": message.date
    })
    logger.info(f"Новый отзыв от {message.from_user.id}: {user_text}")
    await state.clear()
    await message.answer(
        "🙏 Спасибо за ваш отзыв! Он очень важен для ZERG.",
        reply_markup=main_kb
    )

# ---------- Универсальный обработчик всех остальных сообщений ----------
@dp.message()
async def handle_message(message: types.Message, state: FSMContext):
    # Данные из Mini App
    if message.web_app_data:
        data = message.web_app_data.data
        await message.answer(f"📩 Данные из Mini App: {data}")
        return

    if message.text:
        # Если это команда (начинается с "/"), но не обработана выше – заглушка
        if message.text.startswith("/"):
            await message.answer(
                "🔧 СЕЙЧАС ПРОВОДЯТСЯ ТЕХНИЧЕСКИЕ РАБОТЫ,\nприносим свои извинения."
            )
        else:
            # Обычный текст
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

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise
