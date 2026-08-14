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
admin_users = set()      # user_id администраторов
all_users = set()        # все пользователи, кто взаимодействовал с ботом
maintenance_mode = False # флаг режима ТО
maintenance_until = None # время окончания ТО (datetime или None)

# ---------- FSM состояния ----------
class AdminAuth(StatesGroup):
    waiting_for_code = State()

class FeedbackStates(StatesGroup):
    waiting_for_text = State()

class BroadcastStates(StatesGroup):
    waiting_for_text = State()

class MaintenanceStates(StatesGroup):
    waiting_for_duration = State()   # ожидание ввода часов или "off"

# ---------- Клавиатуры ----------
webapp_btn = KeyboardButton(
    text="📱 Открыть приложение",
    web_app=WebAppInfo(url="https://Krasatulkk.github.io/ZERG/")
)
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [webapp_btn],
        [KeyboardButton(text="📝 Отправить отзыв")],
        [KeyboardButton(text="🔐 Войти как администратор")],
        [KeyboardButton(text="ℹ️ Помощь"), KeyboardButton(text="📖 О боте")]
    ],
    resize_keyboard=True
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [webapp_btn],
        [KeyboardButton(text="📝 Отправить отзыв")],
        [KeyboardButton(text="📢 Отправить рассылку")],
        [KeyboardButton(text="🛠 Режим ТО")],
        [KeyboardButton(text="🚪 Выйти из админ-режима")],
        [KeyboardButton(text="ℹ️ Помощь")]
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

# ---------- Обработчик ошибок ----------
@dp.errors()
async def handle_errors(update: types.Update, exception: Exception) -> bool:
    logger.error(f"Ошибка: {exception}", exc_info=True)
    return True

# ---------- Вспомогательная функция проверки режима ТО ----------
async def check_maintenance(message: types.Message) -> bool:
    """Возвращает True, если режим ТО активен и пользователь не админ."""
    if message.from_user.id in admin_users:
        return False  # админам не показываем
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
    await message.answer(
        "👋 Вас приветствует Gehenna AI!\n"
        "Вы в обычном режиме. Для доступа к админ-панели нажмите «Войти как администратор».\n\n"
        "📱 Скачайте Gehenna App для полного функционала: [ссылка на приложение]",
        reply_markup=main_kb
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
        admin_users.add(message.from_user.id)
        all_users.add(message.from_user.id)
        await state.clear()
        await message.answer(
            "✅ Доступ предоставлен! Теперь вы администратор.",
            reply_markup=admin_kb
        )
        logger.info(f"Администратор вошёл: {message.from_user.id}")
    else:
        await message.answer("❌ Неверный код. Попробуйте ещё раз или /cancel.")

# ---------- /logout и кнопка выхода ----------
@dp.message(Command("logout"))
async def cmd_logout(message: types.Message, state: FSMContext):
    if await check_maintenance(message):
        return
    if message.from_user.id in admin_users:
        admin_users.remove(message.from_user.id)
        await state.clear()
        await message.answer(
            "🚪 Вы вышли из админ-режима.",
            reply_markup=main_kb
        )
        logger.info(f"Администратор вышел: {message.from_user.id}")
    else:
        await message.answer("Вы не были в админ-режиме.")

@dp.message(lambda msg: msg.text == "🚪 Выйти из админ-режима")
async def logout_button(message: types.Message, state: FSMContext):
    await cmd_logout(message, state)

# ---------- Обработка отзыва (для всех) ----------
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

@dp.message(StateFilter(FeedbackStates.waiting_for_text))
async def process_feedback(message: types.Message, state: FSMContext):
    if await check_maintenance(message):
        return
    feedback_text = message.text
    if not feedback_text:
        await message.answer("Пожалуйста, напишите текст отзыва.")
        return

    user_id = message.from_user.id
    username = message.from_user.username or "без_имени"
    full_name = message.from_user.full_name or "не указан"

    logger.info(f"Отзыв от {user_id} ({username}): {feedback_text}")

    # Отправляем отзыв всем администраторам
    if admin_users:
        sent_count = 0
        for admin_id in admin_users:
            try:
                await bot.send_message(
                    admin_id,
                    f"📩 **Новый отзыв!**\n\n"
                    f"👤 Пользователь: {full_name} (@{username})\n"
                    f"🆔 ID: {user_id}\n"
                    f"📝 Текст:\n{feedback_text}"
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Не удалось отправить отзыв админу {admin_id}: {e}")
        await message.answer(
            f"🙏 Спасибо за ваш отзыв! Он был отправлен {sent_count} администраторам.\n"
            "Ваше мнение очень важно для ZERG."
        )
    else:
        await message.answer(
            "🙏 Спасибо за ваш отзыв! К сожалению, сейчас нет активных администраторов, но мы обязательно его учтём."
        )

    await state.clear()

# ---------- РАССЫЛКА (только для администраторов) ----------
@dp.message(Command("broadcast"))
async def broadcast_command(message: types.Message, state: FSMContext):
    if await check_maintenance(message):
        return
    if message.from_user.id not in admin_users:
        await message.answer("⛔ Доступ запрещён. Вы не администратор.")
        return
    await state.set_state(BroadcastStates.waiting_for_text)
    await message.answer("📢 Введите текст сообщения для рассылки всем пользователям:")

@dp.message(lambda msg: msg.text == "📢 Отправить рассылку")
async def broadcast_button(message: types.Message, state: FSMContext):
    await broadcast_command(message, state)

@dp.message(StateFilter(BroadcastStates.waiting_for_text))
async def process_broadcast(message: types.Message, state: FSMContext):
    if await check_maintenance(message):
        return
    broadcast_text = message.text
    if not broadcast_text:
        await message.answer("Пожалуйста, введите текст для рассылки.")
        return

    total = len(all_users)
    if total == 0:
        await message.answer("Нет пользователей для рассылки.")
        await state.clear()
        return

    await message.answer(f"⏳ Начинаю рассылку для {total} пользователей...")

    success_count = 0
    fail_count = 0
    for user_id in all_users:
        try:
            text_to_send = f"📢 **Я СЛЫШУ ГОЛОС БОГА:**\n\n{broadcast_text}"
            await bot.send_message(user_id, text_to_send)
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            fail_count += 1
            logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

    await message.answer(
        f"✅ Рассылка завершена!\n"
        f"📨 Успешно отправлено: {success_count}\n"
        f"❌ Не удалось отправить: {fail_count}"
    )
    await state.clear()

# ---------- РЕЖИМ ТЕХНИЧЕСКИХ РАБОТ (только для администраторов) ----------
@dp.message(Command("maintenance"))
async def maintenance_command(message: types.Message, state: FSMContext):
    if message.from_user.id not in admin_users:
        await message.answer("⛔ Доступ запрещён.")
        return
    # Если уже включён, показываем статус
    if maintenance_mode:
        if maintenance_until:
            until_str = maintenance_until.strftime("%d.%m.%Y %H:%M")
            await message.answer(
                f"🛠 Режим ТО уже включён до {until_str}.\n"
                "Чтобы отключить сейчас, отправьте `off`."
            )
        else:
            await message.answer(
                "🛠 Режим ТО включён (без таймера).\n"
                "Чтобы отключить, отправьте `off`."
            )
        await state.set_state(MaintenanceStates.waiting_for_duration)
        return

    await state.set_state(MaintenanceStates.waiting_for_duration)
    await message.answer(
        "🛠 Введите длительность режима ТО в часах (например, `2`) или `off` для отключения."
    )

@dp.message(lambda msg: msg.text == "🛠 Режим ТО")
async def maintenance_button(message: types.Message, state: FSMContext):
    await maintenance_command(message, state)

@dp.message(StateFilter(MaintenanceStates.waiting_for_duration))
async def process_maintenance_duration(message: types.Message, state: FSMContext):
    if message.from_user.id not in admin_users:
        await message.answer("⛔ Доступ запрещён.")
        await state.clear()
        return

    text = message.text.strip().lower()
    if text == "off":
        # Выключение режима
        global maintenance_mode, maintenance_until
        maintenance_mode = False
        maintenance_until = None
        await state.clear()
        await message.answer("✅ Режим ТО отключён.", reply_markup=admin_kb)
        # Уведомляем всех админов (опционально)
        for admin_id in admin_users:
            try:
                await bot.send_message(admin_id, "🔔 Режим ТО отключён администратором.")
            except Exception:
                pass
        return

    try:
        hours = float(text)
        if hours <= 0:
            await message.answer("❌ Введите положительное число часов.")
            return
        # Включаем режим
        global maintenance_mode, maintenance_until
        maintenance_mode = True
        maintenance_until = datetime.datetime.now() + datetime.timedelta(hours=hours)
        await state.clear()
        await message.answer(
            f"🛠 Режим ТО включён на {hours} ч.\n"
            f"Автоматическое отключение в {maintenance_until.strftime('%H:%M %d.%m.%Y')}.",
            reply_markup=admin_kb
        )
        # Уведомляем всех админов
        for admin_id in admin_users:
            try:
                await bot.send_message(
                    admin_id,
                    f"🛠 Включён режим ТО на {hours} ч. (до {maintenance_until.strftime('%H:%M %d.%m.%Y')})"
                )
            except Exception:
                pass
        # Запускаем таймер автоматического отключения
        asyncio.create_task(auto_disable_maintenance(hours))
    except ValueError:
        await message.answer("❌ Введите число (часы) или `off`.")

async def auto_disable_maintenance(hours: float):
    """Автоматически отключает режим ТО через заданное количество часов."""
    await asyncio.sleep(hours * 3600)  # переводим часы в секунды
    global maintenance_mode, maintenance_until
    if maintenance_mode and maintenance_until and datetime.datetime.now() >= maintenance_until:
        maintenance_mode = False
        maintenance_until = None
        logger.info("Режим ТО автоматически отключён по таймеру.")
        # Уведомляем админов
        for admin_id in admin_users:
            try:
                await bot.send_message(admin_id, "🔔 Режим ТО автоматически отключён (время истекло).")
            except Exception:
                pass

# ---------- Обработка обычных текстовых сообщений (не команд) ----------
@dp.message()
async def handle_other_messages(message: types.Message, state: FSMContext):
    # Проверяем режим ТО для всех, кроме админов
    if await check_maintenance(message):
        return

    all_users.add(message.from_user.id)

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

# ---------- /help ----------
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
        "/feedback — оставить отзыв\n"
        "/broadcast — отправить рассылку (только для админов)\n"
        "/maintenance — управление режимом ТО (только для админов)\n"
        "/help — эта справка\n\n"
        "📱 Для работы с ИИ используйте Gehenna App."
    )

# ---------- Запуск ----------
async def main():
    logger.info("🤖 Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
