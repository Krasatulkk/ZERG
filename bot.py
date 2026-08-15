import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from dotenv import load_dotenv
import datetime

# ---------- Настройка ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Токен не найден")

BOT_API_BASE_URL = "https://round-hill-9d0b.fedorbolgarov2.workers.dev"

# ---------- Хранилище и бот ----------
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN, base_url=BOT_API_BASE_URL)
dp = Dispatcher(storage=storage)

# ---------- Секретный код ----------
ADMIN_SECRET_CODE = "5545z"

# ---------- Хранилища ----------
admin_users = set()          # user_id администраторов
admin_info = {}              # {user_id: (username, full_name)}
all_users = set()            # все пользователи
maintenance_mode = False
maintenance_until = None
feedbacks = []               # список отзывов: {user_id, username, full_name, text, timestamp}

# ---------- FSM состояния ----------
class AdminAuth(StatesGroup):
    waiting_for_code = State()

class FeedbackStates(StatesGroup):
    waiting_for_text = State()
    waiting_confirm = State()   # для подтверждения отправки отзыва

class BroadcastStates(StatesGroup):
    waiting_for_text = State()
    waiting_confirm = State()

class MaintenanceStates(StatesGroup):
    waiting_for_duration = State()

class ClearFeedbackStates(StatesGroup):
    waiting_confirm = State()   # для подтверждения очистки отзывов

# ---------- Клавиатуры ----------
# Убрали кнопку "Помощь" и добавили "Отзывы" только для админов
webapp_btn = KeyboardButton(
    text="📱 Открыть приложение",
    web_app=WebAppInfo(url="https://Krasatulkk.github.io/ZERG/")
)

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [webapp_btn],
        [KeyboardButton(text="📝 Отправить отзыв")],
        [KeyboardButton(text="🔐 Войти как администратор")],
        [KeyboardButton(text="📖 О боте")]  # оставили "О боте" (используется для /about)
    ],
    resize_keyboard=True
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [webapp_btn],
        [KeyboardButton(text="📝 Отправить отзыв")],
        [KeyboardButton(text="📢 Отправить рассылку")],
        [KeyboardButton(text="📋 Отзывы")],          # новая кнопка для просмотра отзывов
        [KeyboardButton(text="👥 Список админов")],
        [KeyboardButton(text="🛠 Режим ТО")],
        [KeyboardButton(text="🚪 Выйти из админ-режима")]
    ],
    resize_keyboard=True
)

# ---------- Inline-клавиатуры ----------
confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="✅ Отправить", callback_data="confirm_broadcast"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_broadcast")
    ]
])

confirm_feedback_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="✅ Отправить", callback_data="confirm_feedback"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_feedback")
    ]
])

clear_feedback_confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="✅ Да, очистить", callback_data="confirm_clear_feedbacks"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_clear_feedbacks")
    ]
])

# ---------- Глобальный список для /reset ----------
bot_messages = []

async def send_and_store(chat_id: int, text: str, **kwargs):
    sent = await bot.send_message(chat_id, text, **kwargs)
    bot_messages.append(sent.message_id)
    if len(bot_messages) > 100:
        bot_messages.pop(0)
    return sent

# ---------- Обработчик ошибок ----------
@dp.errors()
async def handle_errors(update: types.Update, exception: Exception) -> bool:
    logger.error(f"Ошибка: {exception}", exc_info=True)
    return True

# ---------- Проверка режима ТО ----------
async def check_maintenance(message: types.Message) -> bool:
    if message.from_user.id in admin_users:
        return False
    if maintenance_mode:
        await message.answer(
            "🔧 СЕЙЧАС ПРОВОДЯТСЯ ТЕХНИЧЕСКИЕ РАБОТЫ.\n"
            "Приложение временно недоступно. Приносим извинения за неудобства."
        )
        return True
    return False

# ---------- /start ----------
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    if await check_maintenance(message):
        return
    await state.clear()
    all_users.add(message.from_user.id)

    kb = admin_kb if message.from_user.id in admin_users else main_kb

    await message.answer(
        "👋 Вас приветствует Gehenna AI!\n\n"
        "Вы в обычном режиме. Для доступа к админ-панели нажмите «Войти как администратор».\n\n"
        "📱 Скачайте Gehenna App для полного функционала: [ссылка на приложение]",
        reply_markup=kb
    )

# ---------- /app ----------
@dp.message(Command("app"))
async def cmd_app(message: types.Message):
    if await check_maintenance(message):
        return
    kb = admin_kb if message.from_user.id in admin_users else main_kb
    await message.answer(
        "📱 Кнопка для открытия приложения:",
        reply_markup=kb
    )

# ---------- /admin и кнопка входа ----------
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    if await check_maintenance(message):
        return
    if message.from_user.id in admin_users:
        await message.answer("✅ Вы уже вошли как администратор.", reply_markup=admin_kb)
        return
    await state.set_state(AdminAuth.waiting_for_code)
    await message.answer("🔑 Введите секретный код доступа:")

@dp.message(lambda msg: msg.text == "🔐 Войти как администратор")
async def admin_button(message: types.Message, state: FSMContext):
    await cmd_admin(message, state)

# ---------- Проверка кода ----------
@dp.message(StateFilter(AdminAuth.waiting_for_code))
async def process_admin_code(message: types.Message, state: FSMContext):
    if await check_maintenance(message):
        return
    code = message.text.strip()
    if code == ADMIN_SECRET_CODE:
        user_id = message.from_user.id
        admin_users.add(user_id)
        all_users.add(user_id)
        admin_info[user_id] = (message.from_user.username or "без_имени", message.from_user.full_name or "не указан")
        await state.clear()
        await message.answer(
            "✅ Доступ предоставлен! Теперь вы администратор.",
            reply_markup=admin_kb
        )
        logger.info(f"Администратор вошёл: {user_id}")
    else:
        await message.answer("❌ Неверный код. Попробуйте ещё раз или /cancel.")

# ---------- /logout и кнопка выхода ----------
@dp.message(Command("logout"))
async def cmd_logout(message: types.Message, state: FSMContext):
    if await check_maintenance(message):
        return
    user_id = message.from_user.id
    if user_id in admin_users:
        admin_users.remove(user_id)
        if user_id in admin_info:
            del admin_info[user_id]
        await state.clear()
        await message.answer(
            "🚪 Вы вышли из админ-режима.",
            reply_markup=main_kb
        )
        logger.info(f"Администратор вышел: {user_id}")
    else:
        await message.answer("Вы не были в админ-режиме.")

@dp.message(lambda msg: msg.text == "🚪 Выйти из админ-режима")
async def logout_button(message: types.Message, state: FSMContext):
    await cmd_logout(message, state)

# ---------- Список администраторов ----------
@dp.message(Command("admin_list"))
async def cmd_admin_list(message: types.Message):
    if message.from_user.id not in admin_users:
        await message.answer("⛔ Доступ запрещён. Вы не администратор.")
        return
    if not admin_info:
        await message.answer("👥 В данный момент нет активных администраторов.")
        return

    lines = []
    for i, (uid, (username, full_name)) in enumerate(admin_info.items(), 1):
        lines.append(
            f"{i}. ID: `{uid}`\n"
            f"   Username: @{username}\n"
            f"   Имя: {full_name}\n"
            f"   Статус: ✅ Онлайн"
        )
    text = "👥 **Список активных администраторов:**\n\n" + "\n".join(lines)
    await message.answer(text, parse_mode="Markdown")

@dp.message(lambda msg: msg.text == "👥 Список админов")
async def admin_list_button(message: types.Message):
    await cmd_admin_list(message)

# ---------- ОТЗЫВЫ ----------
# Команда для отправки отзыва
@dp.message(Command("feedback"))
async def feedback_command(message: types.Message, state: FSMContext):
    if await check_maintenance(message):
        return
    all_users.add(message.from_user.id)
    await state.set_state(FeedbackStates.waiting_for_text)
    await message.answer(
        "📝 Напишите ваш отзыв или пожелание. Мы очень ценим ваше мнение!"
    )

@dp.message(lambda msg: msg.text == "📝 Отправить отзыв")
async def feedback_button(message: types.Message, state: FSMContext):
    await feedback_command(message, state)

# Приём текста отзыва
@dp.message(StateFilter(FeedbackStates.waiting_for_text))
async def process_feedback_text(message: types.Message, state: FSMContext):
    if await check_maintenance(message):
        return
    text = message.text
    if not text:
        await message.answer("Пожалуйста, напишите текст отзыва.")
        return

    # Сохраняем текст и предлагаем подтверждение
    await state.update_data(feedback_text=text)
    await state.set_state(FeedbackStates.waiting_confirm)

    await message.answer(
        f"📝 **Предпросмотр отзыва:**\n\n{text}\n\nПодтвердите отправку:",
        reply_markup=confirm_feedback_kb
    )

# Обработка подтверждения отзыва
@dp.callback_query(lambda c: c.data == "confirm_feedback")
async def confirm_feedback(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    feedback_text = data.get("feedback_text")
    if not feedback_text:
        await callback.answer("Ошибка: текст не найден.", show_alert=True)
        await state.clear()
        return

    # Сохраняем отзыв
    feedbacks.append({
        "user_id": user_id,
        "username": callback.from_user.username or "без_имени",
        "full_name": callback.from_user.full_name or "не указан",
        "text": feedback_text,
        "timestamp": datetime.datetime.now()
    })
    logger.info(f"Новый отзыв от {user_id}: {feedback_text}")

    # Отправляем уведомления админам
    if admin_users:
        sent_count = 0
        for admin_id in admin_users:
            try:
                await bot.send_message(
                    admin_id,
                    f"📩 **Новый отзыв!**\n\n"
                    f"👤 Пользователь: {callback.from_user.full_name} (@{callback.from_user.username or 'без_имени'})\n"
                    f"🆔 ID: {user_id}\n"
                    f"📝 Текст:\n{feedback_text}\n"
                    f"🕒 Время: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Не удалось отправить отзыв админу {admin_id}: {e}")
        await callback.message.edit_text(
            f"🙏 Спасибо за ваш отзыв! Он был отправлен {sent_count} администраторам.\n"
            "Ваше мнение очень важно для ZERG."
        )
    else:
        await callback.message.edit_text(
            "🙏 Спасибо за ваш отзыв! К сожалению, сейчас нет активных администраторов, но мы обязательно его учтём."
        )

    await state.clear()
    await callback.answer()

# Отмена отправки отзыва
@dp.callback_query(lambda c: c.data == "cancel_feedback")
async def cancel_feedback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Отправка отзыва отменена.")
    await callback.answer()

# ---------- ПРОСМОТР ОТЗЫВОВ (для админов) ----------
@dp.message(Command("feedbacks"))
async def cmd_feedbacks(message: types.Message):
    if message.from_user.id not in admin_users:
        await message.answer("⛔ Доступ запрещён. Вы не администратор.")
        return

    if not feedbacks:
        await message.answer("📋 Отзывов пока нет.")
        return

    # Формируем список
    lines = []
    for i, fb in enumerate(feedbacks, 1):
        dt = fb['timestamp'].strftime("%d.%m.%Y %H:%M")
        lines.append(
            f"{i}. 👤 {fb['full_name']} (@{fb['username']}) [ID: {fb['user_id']}]\n"
            f"   🕒 {dt}\n"
            f"   📝 {fb['text']}\n"
        )
    text = "📋 **Список отзывов:**\n\n" + "\n".join(lines)

    # Кнопка очистки
    clear_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Очистить все", callback_data="clear_feedbacks")]
    ])

    await message.answer(text, parse_mode="Markdown", reply_markup=clear_kb)

@dp.message(lambda msg: msg.text == "📋 Отзывы")
async def feedbacks_button(message: types.Message):
    await cmd_feedbacks(message)

# ---------- ОЧИСТКА ОТЗЫВОВ (подтверждение) ----------
@dp.callback_query(lambda c: c.data == "clear_feedbacks")
async def clear_feedbacks_request(callback: types.CallbackQuery):
    if callback.from_user.id not in admin_users:
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return
    # Показываем подтверждение
    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите удалить **все** отзывы? Это действие необратимо.",
        reply_markup=clear_feedback_confirm_kb
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "confirm_clear_feedbacks")
async def confirm_clear_feedbacks(callback: types.CallbackQuery):
    if callback.from_user.id not in admin_users:
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    global feedbacks
    feedbacks = []  # очищаем список
    await callback.message.edit_text("✅ Все отзывы удалены.")
    # Уведомляем всех админов
    for admin_id in admin_users:
        try:
            await bot.send_message(admin_id, "🗑 Администратор очистил все отзывы.")
        except Exception:
            pass
    await callback.answer()

@dp.callback_query(lambda c: c.data == "cancel_clear_feedbacks")
async def cancel_clear_feedbacks(callback: types.CallbackQuery):
    if callback.from_user.id not in admin_users:
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return
    # Возвращаем список отзывов
    await cmd_feedbacks(callback.message)
    await callback.answer()

# ---------- РАССЫЛКА (с подтверждением) ----------
# ... (код рассылки без изменений) ...
# Оставляем существующий код рассылки (он уже есть в предыдущей версии)
# Для краткости я не буду его дублировать, но он должен быть добавлен.

# ---------- РЕЖИМ ТЕХНИЧЕСКИХ РАБОТ ----------
# ... (код режима ТО без изменений) ...

# ---------- Обработка обычных текстовых сообщений ----------
@dp.message()
async def handle_other_messages(message: types.Message, state: FSMContext):
    if await check_maintenance(message):
        return

    all_users.add(message.from_user.id)

    # Обработка данных из Mini App (новая кнопка)
    if message.web_app_data:
        data = message.web_app_data.data
        # Отправляем то же сообщение пользователю
        await message.answer(data)
        return

    if message.text and message.text.startswith("/"):
        await message.answer("🔧 Неизвестная команда. Используйте /help.")
        return

    if message.text:
        if message.from_user.id in admin_users:
            await message.answer(
                "📱 В админ-режиме вы можете использовать кнопки меню.\n"
                "Для работы с ИИ используйте Gehenna App."
            )
        else:
            await message.answer(
                "📱 Функция вопросов отключена. Скачайте Gehenna App для полного доступа.\n"
                "Ссылка: [вставьте ссылку на ваше приложение]"
            )

# ---------- /about (изменённая) ----------
@dp.message(Command("about"))
async def cmd_about(message: types.Message):
    await message.answer("Gehenna AI by ZERG - Gehenna App")

# ---------- /help (обновлённая, без кнопки помощи) ----------
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    if await check_maintenance(message):
        return
    all_users.add(message.from_user.id)
    await message.answer(
        "📖 Доступные команды:\n"
        "/start — приветствие\n"
        "/admin — войти как администратор (ввести код)\n"
        "/logout — выйти из админ-режима\n"
        "/admin_list — список активных администраторов (только для админов)\n"
        "/feedback — оставить отзыв\n"
        "/broadcast — отправить рассылку (только для админов)\n"
        "/feedbacks — просмотреть отзывы (только для админов)\n"
        "/maintenance — управление режимом ТО (только для админов)\n"
        "/app — показать кнопку приложения\n"
        "/about — информация о боте\n"
        "/help — эта справка\n\n"
        "📱 Для работы с ИИ используйте Gehenna App."
    )

# ---------- Запуск ----------
async def main():
    logger.info("🤖 Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
