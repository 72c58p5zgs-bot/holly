from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
import asyncio
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

from database import (
    init_db,
    add_quote,
    get_random_quote,
    get_all_quotes,
    add_sent_message,
    clear_old_records,
    get_messages_for_date,
)

# --- Настройки ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в .env")
if not CHAT_ID:
    raise ValueError("CHAT_ID не установлен в .env")

# Часовой пояс — Москва
TIMEZONE = "Europe/Moscow"

# --- Вариации сообщений ---
MORNING_MESSAGES = [
    "Доброе утро, солнышко! Пусть день будет таким же ярким, как твоя улыбка — и пусть всё получается с легкостью! ☀️✨",
    "Просыпайся, чемпион! Сегодня точно твой день — впереди куча крутых возможностей, а я в тебя верю на все 100 %! 💪😄",
    "Доброе утро! Пусть кофе будет крепким, настроение — отличным, а все задачи решаются легко и с улыбкой. Ты всё сможешь! ☕😊",
    "Эй, привет! Желаю тебе такого утра, чтобы с первой минуты захотелось улыбаться, а каждый следующий час приносил что‑то приятное. Вперёд к победам! 🌟",
    "Доброе утро, чудо! Пусть сегодня всё складывается как надо: люди будут добрыми, дела — лёгкими, а сюрпризы — только приятными. Удачи и отличного настроения! 🤗💫",
    "Подъём, супергерой! Новый день — новые подвиги (хотя бы успеть сделать всё запланированное 😄). Пусть энергия бьёт ключом, а мотивация не подводит. Вперёд! 🚀",
    "Доброе утро! Желаю тебе море позитива, гору вдохновения и океан удачи. Пусть день будет полон приятных моментов, а трудности обходят стороной. Ты на верном пути! 🌈😊",
    "Новый день — новые возможности! 💪 Доброе утро!"
]

EVENING_MESSAGES = [
    "Спокойной ночи, звёздочка! Пусть сны будут тёплыми и сказочными, а утро — бодрым и солнечным. Отдыхай как следует! ✨🌙",
    "Доброй ночи, дружище! Закрой глаза и забудь про все заботы — завтра будет новый день и новые победы. Пусть тебе снятся самые сладкие сны! 😴💫",
    "Сладких снов! Пусть подушка будет мягкой, одеяло — тёплым, а мысли — лёгкими и приятными. Отдыхай по полной, завтра тебя ждёт что‑то хорошее! 🛌❤️",
    "Время спать, герой! День был крутым, ты молодец, теперь пора восстановить силы. Пусть ночь подарит тебе крепкий сон и заряд энергии на завтра. Спокойной ночи! 🌌💤",
    "Доброй ночи! Желаю тебе погрузиться в океан самых уютных снов, где нет тревог, а есть только тепло, радость и волшебство. Отдыхай и набирайся сил! 🌊✨",
    "Закрывай глазки, солнышко! Пусть ночь укроет тебя мягким покрывалом тишины, а сны принесут что‑то доброе и светлое. Завтра будет ещё лучше — обещаю! 🌠😴",
    "Спокойной ночи, моя хорошая! Пусть все тревоги останутся за дверью, а внутри будет только покой и уют. Спи крепко, отдыхай душой и телом — завтра ждёт новый замечательный день! 🛏️🌛",
    "Заверши день с благодарностью. Спокойной ночи! 🌌"
]

# --- Инициализация бота ---
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler(timezone=TIMEZONE)


# --- Функция-обёртка для отправки и сохранения ID ---
async def send_and_log(text: str) -> None:
    """Отправляет сообщение и сохраняет его ID в БД"""
    msg = await bot.send_message(CHAT_ID, text)
    add_sent_message(msg.message_id, CHAT_ID)


# --- FSM для добавления цитат ---
class QuoteState(StatesGroup):
    waiting_for_quote = State()
    waiting_for_quotes = State()


# --- Команды ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await send_and_log(
        "Привет! Я мотивационный бот 🌟\n"
        "Каждый день я буду присылать тебе цитаты, а утром и вечером — пожелания.\n\n"
        "Команды:\n"
        "/addquote — добавить цитату\n"
        "/addquotes — добавить несколько цитат (по одной на строку)\n"
        "/random — получить случайную цитату сейчас\n"
        "/all — посмотреть все цитаты"
    )


@dp.message(Command("addquote"))
async def cmd_addquote(message: Message, state: FSMContext):
    await message.answer("Напиши цитату, которую хочешь добавить:")
    await state.set_state(QuoteState.waiting_for_quote)


@dp.message(QuoteState.waiting_for_quote)
async def process_quote(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) < 5:
        await message.answer("Цитата слишком короткая. Попробуй ещё раз.")
        return
    add_quote(text)
    await send_and_log("✅ Цитата добавлена!")
    await state.clear()


@dp.message(Command("addquotes"))
async def cmd_addquotes(message: Message, state: FSMContext):
    await message.answer(
        "Отправь список цитат. Каждую цитату пиши с новой строки.\n\n"
        "Пример:\n"
        "Цель — это мечта с ограниченным сроком.\n"
        "Успех — это сумма маленьких усилий.\n"
        "Ты должен начать, чтобы быть великим."
    )
    await state.set_state(QuoteState.waiting_for_quotes)


@dp.message(QuoteState.waiting_for_quotes)
async def process_bulk_quotes(message: Message, state: FSMContext):
    text = message.text.strip()
    quotes = [q.strip() for q in text.split('\n') if q.strip()]

    if len(quotes) == 0:
        await send_and_log("❌ Не найдено ни одной цитаты.")
        return

    added = 0
    for quote in quotes:
        if len(quote) >= 5:
            add_quote(quote)
            added += 1

    await send_and_log(f"✅ Успешно добавлено цитат: {added}")
    await state.clear()


@dp.message(Command("random"))
async def cmd_random(message: Message):
    quote = get_random_quote()
    await send_and_log(f"✨ Вот твоя цитата:\n\n{quote}")


@dp.message(Command("all"))
async def cmd_all(message: Message):
    quotes = get_all_quotes()
    if not quotes:
        await send_and_log("База цитат пуста.")
        return
    response = "\n\n".join([f"💬 {q}" for q in quotes])
    await send_and_log(f"Все цитаты ({len(quotes)} шт.):\n\n{response}")


# --- Автоматические рассылки ---
async def send_morning_message():
    text = random.choice(MORNING_MESSAGES)
    await send_and_log(text)


async def send_evening_message():
    text = random.choice(EVENING_MESSAGES)
    await send_and_log(text)


async def send_daily_quote():
    quote = get_random_quote()
    await send_and_log(f"{quote}")


# --- Удаление вчерашних сообщений ---
async def delete_yesterday_messages():
    from datetime import datetime, timedelta
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    message_ids = get_messages_for_date(CHAT_ID, yesterday)

    deleted_count = 0
    for msg_id in message_ids:
        try:
            await bot.delete_message(CHAT_ID, msg_id)
            deleted_count += 1
        except Exception as e:
            print(f"Не удалось удалить сообщение {msg_id}: {e}")

    if deleted_count > 0:
        await send_and_log(f"🧹 Удалено {deleted_count} сообщений за {yesterday}")

    # Чистка старых записей в БД
    clear_old_records()


# --- Планировщик ---
def setup_scheduler():
    tz = TIMEZONE
    
   # 🌅 Утренние пожелания — можно указать несколько раз
    scheduler.add_job(send_morning_message, CronTrigger(hour=9, minute=0, timezone=tz))
    # scheduler.add_job(send_morning_message, CronTrigger(hour=9, minute=0, timezone=tz))

    # 🌙 Вечерние пожелания
    scheduler.add_job(send_evening_message, CronTrigger(hour=22, minute=0, timezone=tz))
    # scheduler.add_job(send_evening_message, CronTrigger(hour=23, minute=30, timezone=tz))
    
    # Рассылки
    scheduler.add_job(send_daily_quote, CronTrigger(hour=10, minute=10, timezone=tz))
    scheduler.add_job(send_daily_quote, CronTrigger(hour=11, minute=11, timezone=tz))
    scheduler.add_job(send_daily_quote, CronTrigger(hour=12, minute=12, timezone=tz))
    scheduler.add_job(send_daily_quote, CronTrigger(hour=13, minute=13, timezone=tz))
    scheduler.add_job(send_daily_quote, CronTrigger(hour=14, minute=14, timezone=tz))
    scheduler.add_job(send_daily_quote, CronTrigger(hour=15, minute=15, timezone=tz))
    scheduler.add_job(send_daily_quote, CronTrigger(hour=16, minute=16, timezone=tz))
    scheduler.add_job(send_daily_quote, CronTrigger(hour=17, minute=17, timezone=tz))
    scheduler.add_job(send_daily_quote, CronTrigger(hour=18, minute=18, timezone=tz))
    scheduler.add_job(send_daily_quote, CronTrigger(hour=19, minute=19, timezone=tz))
    scheduler.add_job(send_daily_quote, CronTrigger(hour=20, minute=20, timezone=tz))
    scheduler.add_job(send_daily_quote, CronTrigger(hour=21, minute=21, timezone=tz))
    

    # Очистка — в 00:05 каждый день
    scheduler.add_job(delete_yesterday_messages, CronTrigger(hour=0, minute=5, timezone=tz))


# --- Запуск бота ---
async def main():
    init_db()
    setup_scheduler()
    scheduler.start()
    print("✅ Бот запущен и готов к работе...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
