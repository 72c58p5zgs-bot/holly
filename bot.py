from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message  # ← ЭТОТ ИМПОРТ БЫЛ НЕ ХВАТАЕТ!
import asyncio
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

from database import init_db, add_quote, get_random_quote, get_all_quotes

# --- Настройки ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в .env")
if not CHAT_ID:
    raise ValueError("CHAT_ID не установлен в .env")

# Часовой пояс — фиксирован: Москва
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

# --- FSM для добавления цитаты ---
class QuoteState(StatesGroup):
    waiting_for_quote = State()

# --- Команды ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я мотивационный бот 🌟\n"
        "Каждый день я буду присылать тебе цитаты, а утром и вечером — пожелания.\n\n"
        "Команды:\n"
        "/addquote — добавить цитату\n"
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
    await message.answer("✅ Цитата добавлена!")
    await state.clear()

@dp.message(Command("random"))
async def cmd_random(message: Message):
    quote = get_random_quote()
    await message.answer(f"✨ Вот твоя цитата:\n\n{quote}")

@dp.message(Command("all"))
async def cmd_all(message: Message):
    quotes = get_all_quotes()
    if not quotes:
        await message.answer("База цитат пуста.")
        return
    response = "\n\n".join([f"💬 {q}" for q in quotes])
    await message.answer(f"Все цитаты ({len(quotes)} шт.):\n\n{response}")

# --- Функции рассылки ---
async def send_morning_message():
    text = random.choice(MORNING_MESSAGES)
    await bot.send_message(CHAT_ID, text)

async def send_evening_message():
    text = random.choice(EVENING_MESSAGES)
    await bot.send_message(CHAT_ID, text)

async def send_daily_quote():
    quote = get_random_quote()
    await bot.send_message(CHAT_ID, f"📌 Твоя цитата дня:\n\n{quote}")

# --- Настройка времени отправки ---
def setup_scheduler():
    tz = TIMEZONE  # Москва

    # 🌅 Утренние пожелания — можно указать несколько раз
    scheduler.add_job(send_morning_message, CronTrigger(hour=9, minute=0, timezone=tz))
    # scheduler.add_job(send_morning_message, CronTrigger(hour=9, minute=0, timezone=tz))

    # 🌙 Вечерние пожелания
    scheduler.add_job(send_evening_message, CronTrigger(hour=22, minute=0, timezone=tz))
    # scheduler.add_job(send_evening_message, CronTrigger(hour=23, minute=30, timezone=tz))

    # 💬 Цитаты в течение дня — сколько угодно точек
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
    # Пример: раскомментируй, чтобы добавить ещё:
    # scheduler.add_job(send_daily_quote, CronTrigger(hour=16, minute=30, timezone=tz))

# --- Запуск бота ---
async def main():
    init_db()           # Создаём БД при старте
    setup_scheduler()   # Настраиваем расписание
    scheduler.start()   # Запускаем планировщик
    print("✅ Бот запущен и готов к работе...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
