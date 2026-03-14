import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    FSInputFile,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import sqlite3

# === НАСТРОЙКИ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
YOUR_USER_ID = int(os.getenv("YOUR_USER_ID"))
DB_FILE = "recipes.db"
# =================

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

# --- Постоянная клавиатура ---
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📚 Каталог"),
                KeyboardButton(text="🧮 Калькулятор"),
            ],
            [
                KeyboardButton(text="🥩 Белок"),
                KeyboardButton(text="➕ Добавить рецепт"),
            ],
            [
                KeyboardButton(text="🔍 Поиск"),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

# --- Инициализация БД ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            category TEXT,
            ingredients TEXT,
            steps TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_data (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    cur.execute("INSERT OR IGNORE INTO user_data (key, value) VALUES (?, ?)", ("protein_goal", "100"))
    cur.execute("INSERT OR IGNORE INTO user_data (key, value) VALUES (?, ?)", ("protein_today", "0"))
    conn.commit()
    conn.close()

def get_db():
    return sqlite3.connect(DB_FILE)

# --- FSM ---
class RecipeState(StatesGroup):
    waiting_for_name = State()
    waiting_for_category = State()
    waiting_for_ingredients = State()
    waiting_for_steps = State()

class ProteinState(StatesGroup):
    waiting_for_protein_per_100 = State()
    waiting_for_weight = State()

# --- /start ---
@dp.message(Command("start"))
async def start(message: Message):
    if message.from_user.id != YOUR_USER_ID:
        return
    init_db()
    await message.answer(
        "🍳 Добро пожаловать в Книгу рецептов!\n\n"
        "📌 Используйте кнопки внизу:",
        reply_markup=get_main_menu()
    )

# --- Быстрые кнопки ---
@dp.message(F.text == "📚 Каталог")
async def quick_catalog(message: Message):
    if message.from_user.id != YOUR_USER_ID:
        return
    await show_catalog(message)

@dp.message(F.text == "🧮 Калькулятор")
async def quick_calculator(message: Message, state: FSMContext):
    if message.from_user.id != YOUR_USER_ID:
        return
    await protein_portion_start(message, state)

@dp.message(F.text == "🥩 Белок")
async def quick_protein(message: Message):
    if message.from_user.id != YOUR_USER_ID:
        return
    await show_protein_stats(message)

@dp.message(F.text == "➕ Добавить рецепт")
async def quick_add_recipe(message: Message, state: FSMContext):
    if message.from_user.id != YOUR_USER_ID:
        return
    await add_recipe_start(message, state)

@dp.message(F.text == "🔍 Поиск")
async def search_prompt(message: Message):
    if message.from_user.id != YOUR_USER_ID:
        return
    await message.answer("🔎 Введите ингредиент для поиска (например: *чеснок*, *сыр*, *рис*)", parse_mode="Markdown")

# === УЧЁТ БЕЛКА ===
async def show_protein_stats(message: Message):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM user_data WHERE key = 'protein_goal'")
    goal = int(cur.fetchone()[0])
    cur.execute("SELECT value FROM user_data WHERE key = 'protein_today'")
    today = float(cur.fetchone()[0])
    conn.close()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Внести белок", callback_data="add_p")]
    ])
    await message.answer(
        f"📊 Белок за день:\n\n"
        f"🎯 Цель: {goal} г\n"
        f"✅ Внесено: {today:.1f} г\n"
        f"📊 Осталось: {max(0, goal - today):.1f} г",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "add_p")
async def ask_protein_amount(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Сколько грамм белка добавить?", reply_markup=get_main_menu())
    await state.set_state(ProteinState.waiting_for_weight)

@dp.message(ProteinState.waiting_for_weight)
async def handle_protein_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("Введите число > 0", reply_markup=get_main_menu())
            return
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT value FROM user_data WHERE key = 'protein_today'")
        current = float(cur.fetchone()[0])
        new = current + amount
        cur.execute("UPDATE user_data SET value = ? WHERE key = 'protein_today'", (str(new),))
        conn.commit()
        conn.close()
        goal = int(get_db().execute("SELECT value FROM user_data WHERE key = 'protein_goal'").fetchone()[0])
        await message.answer(
            f"✅ Добавлено {amount} г белка.\n"
            f"📊 Всего: {new:.1f} г из {goal} г",
            reply_markup=get_main_menu()
        )
        await state.clear()
    except:
        await message.answer("Введите число, например: 30", reply_markup=get_main_menu())

# --- Калькулятор белка ---
@dp.message(Command("protein_portion"))
async def protein_portion_start(message: Message, state: FSMContext):
    if message.from_user.id != YOUR_USER_ID:
        return
    await message.answer("Сколько грамм белка в 100 г продукта?", reply_markup=get_main_menu())
    await state.set_state(ProteinState.waiting_for_protein_per_100)

@dp.message(ProteinState.waiting_for_protein_per_100)
async def protein_per_100(message: Message, state: FSMContext):
    try:
        protein_per_100 = float(message.text)
        if protein_per_100 < 0:
            await message.answer("Число не может быть отрицательным.", reply_markup=get_main_menu())
            return
        await state.update_data(protein_per_100=protein_per_100)
        await message.answer("Сколько грамм порция?", reply_markup=get_main_menu())
        await state.set_state(ProteinState.waiting_for_weight)
    except:
        await message.answer("Введите число, например: 20", reply_markup=get_main_menu())

@dp.message(ProteinState.waiting_for_weight)
async def protein_weight(message: Message, state: FSMContext):
    try:
        weight = float(message.text)
        if weight <= 0:
            await message.answer("Вес должен быть больше 0.", reply_markup=get_main_menu())
            return
        data = await state.get_data()
        protein_per_100 = data["protein_per_100"]
        protein = (protein_per_100 / 100) * weight
        protein = round(protein, 1)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Добавить к дневному", callback_data=f"apc_{protein}")],
            [InlineKeyboardButton(text="❌ Не добавлять", callback_data="cancel_apc")],
        ])
        await message.answer(
            f"🍽 Порция: {weight} г\n"
            f"🥩 Белка: {protein_per_100} г / 100 г\n"
            f"📊 Итого: {protein} г белка",
            reply_markup=keyboard
        )
        await state.clear()
    except:
        await message.answer("Введите число, например: 150", reply_markup=get_main_menu())

@dp.callback_query(F.data.startswith("apc_"))
async def confirm_add_protein(callback: CallbackQuery):
    protein = float(callback.data.split("_", 1)[1])
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM user_data WHERE key = 'protein_today'")
    current = float(cur.fetchone()[0])
    new = current + protein
    cur.execute("UPDATE user_data SET value = ? WHERE key = 'protein_today'", (str(new),))
    conn.commit()
    conn.close()
    goal = int(get_db().execute("SELECT value FROM user_data WHERE key = 'protein_goal'").fetchone()[0])
    await callback.message.edit_text(f"✅ Добавлено {protein} г белка.\n📊 Всего: {new:.1f} г из {goal} г")
    await callback.answer()

@dp.callback_query(F.data == "cancel_apc")
async def cancel_add_protein(callback: CallbackQuery):
    await callback.message.edit_text("❌ Белок не добавлен.")
    await callback.answer()

# === КАТАЛОГ С ПАГИНАЦИЕЙ ===
RECIPES_PER_PAGE = 6

@dp.message(Command("catalog"))
async def show_catalog(message: Message):
    if message.from_user.id != YOUR_USER_ID:
        return
    await send_category_menu(message)

async def send_category_menu(message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍳 Завтраки", callback_data="c_b")],
        [InlineKeyboardButton(text="🍚 Гарниры", callback_data="c_s")],
        [InlineKeyboardButton(text="🍛 Основные блюда", callback_data="c_m")],
        [InlineKeyboardButton(text="🥗 Салаты", callback_data="c_d")],
    ])
    if isinstance(message, Message):
        await message.answer("Выберите категорию:", reply_markup=keyboard)
    else:
        await message.edit_text("Выберите категорию:", reply_markup=keyboard)

@dp.callback_query(F.data.in_(["c_b", "c_s", "c_m", "c_d"]))
async def show_category_recipes(callback: CallbackQuery):
    await callback.answer()
    await show_category_page(callback, category_key=callback.data, page=1)

@dp.callback_query(F.data.startswith("page_"))
async def paginate_category(callback: CallbackQuery):
    await callback.answer()
    data = callback.data
    last_underscore = data.rfind("_")
    if last_underscore == -1 or last_underscore == len(data) - 1:
        await callback.message.edit_text("❌ Ошибка: неверный формат данных.")
        return
    category_key = data[5:last_underscore]
    page_str = data[last_underscore + 1:]
    try:
        page = int(page_str)
        if page < 1:
            raise ValueError
    except:
        await callback.message.edit_text("❌ Неверный номер страницы.")
        return
    await show_category_page(callback, category_key, page)

async def show_category_page(callback: CallbackQuery, category_key: str, page: int):
    category_map = {
        "c_b": "завтрак",
        "c_s": "гарнир",
        "c_m": "основное блюдо",
        "c_d": "салат"
    }
    db_category = category_map.get(category_key)
    if not db_category:
        await callback.message.edit_text("❌ Неизвестная категория.")
        return

    label_map = {
        "c_b": "🍳 Завтраки",
        "c_s": "🍚 Гарниры",
        "c_m": "🍛 Основные блюда",
        "c_d": "🥗 Салаты"
    }
    category_label = label_map[category_key]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name FROM recipes WHERE category = ? ORDER BY name", (db_category,))
    all_recipes = [row[0] for row in cur.fetchall()]
    conn.close()

    total_pages = (len(all_recipes) + RECIPES_PER_PAGE - 1) // RECIPES_PER_PAGE
    if total_pages == 0:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_catalog")]
        ])
        await callback.message.edit_text(f"📌 Нет рецептов в категории **{category_label}**.", reply_markup=keyboard)
        return

    page = max(1, min(page, total_pages))
    start = (page - 1) * RECIPES_PER_PAGE
    end = start + RECIPES_PER_PAGE
    recipes_on_page = all_recipes[start:end]

    keyboard = []
    for name in recipes_on_page:
        callback_data = f"r_{name[:60]}"
        disp_name = name if len(name) <= 50 else name[:47] + "..."
        keyboard.append([InlineKeyboardButton(text=f"🍽 {disp_name}", callback_data=callback_data)])

    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"page_{category_key}_{page-1}"))
    pagination_buttons.append(InlineKeyboardButton(text=f"{page} из {total_pages}", callback_data="noop"))
    if page < total_pages:
        pagination_buttons.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"page_{category_key}_{page+1}"))
    keyboard.append(pagination_buttons)
    keyboard.append([InlineKeyboardButton(text="⬅️ К категориям", callback_data="back_to_catalog")])

    await callback.message.edit_text(
        f"📌 {category_label} | Страница {page} из {total_pages}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@dp.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    await callback.answer()

@dp.callback_query(F.data == "back_to_catalog")
async def back_to_catalog(callback: CallbackQuery):
    await callback.answer()
    await send_category_menu(callback.message)

# === ПРОСМОТР РЕЦЕПТА ===
@dp.callback_query(F.data.startswith("r_"))
async def show_recipe(callback: CallbackQuery):
    await callback.answer()
    recipe_name = callback.data[2:]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT category, ingredients, steps FROM recipes WHERE name = ?", (recipe_name,))
    row = cur.fetchone()
    conn.close()

    if not row:
        await callback.message.edit_text("❌ Рецепт не найден.")
        return

    category, ingredients, steps = row
    ingredients_display = "Не требуются" if category in ["гарнир", "завтрак"] else (ingredients.strip() if ingredients.strip() else "—")
    steps_text = steps.strip() if steps.strip() else "—"

    text = f"📝 **{recipe_name}**\n📌 Категория: {category}\n\n"
    if ingredients_display != "—":
        text += f"🧾 **Ингредиенты**:\n{ingredients_display}\n\n"
    text += f"👨‍🍳 **Приготовление**:\n{steps_text}"

    reverse_map = {
        "завтрак": "c_b",
        "гарнир": "c_s",
        "основное блюдо": "c_m",
        "салат": "c_d"
    }
    back_callback = reverse_map.get(category, "back_to_catalog")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_{recipe_name[:60]}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)],
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("del_"))
async def confirm_delete_recipe(callback: CallbackQuery):
    await callback.answer()
    recipe_name = callback.data[4:]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data=f"cdel_{recipe_name[:60]}")],
        [InlineKeyboardButton(text="❌ Нет", callback_data=f"r_{recipe_name[:60]}")],
    ])
    await callback.message.edit_text(f"Удалить рецепт **{recipe_name}**?", reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("cdel_"))
async def delete_recipe_final(callback: CallbackQuery):
    await callback.answer()
    recipe_name = callback.data[5:]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM recipes WHERE name = ?", (recipe_name,))
    conn.commit()
    conn.close()
    await callback.message.edit_text(f"🗑 Рецепт **{recipe_name}** удалён.", parse_mode="Markdown")
    await asyncio.sleep(1)
    await send_category_menu(callback.message)

# === ДОБАВЛЕНИЕ РЕЦЕПТА ===
@dp.message(Command("add_recipe"))
async def add_recipe_start(message: Message, state: FSMContext):
    if message.from_user.id != YOUR_USER_ID:
        return
    await message.answer("🍽 Введите название рецепта:", reply_markup=get_main_menu())
    await state.set_state(RecipeState.waiting_for_name)

@dp.message(RecipeState.waiting_for_name)
async def recipe_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("❌ Название не может быть пустым.")
        return
    await state.update_data(name=name)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍳 Завтрак", callback_data="n_b")],
        [InlineKeyboardButton(text="🍚 Гарнир", callback_data="n_s")],
        [InlineKeyboardButton(text="🍛 Основное", callback_data="n_m")],
        [InlineKeyboardButton(text="🥗 Салат", callback_data="n_d")],
    ])
    await message.answer("📌 Выберите категорию:", reply_markup=keyboard)
    await state.set_state(RecipeState.waiting_for_category)

@dp.callback_query(F.data.in_(["n_b", "n_s", "n_m", "n_d"]), RecipeState.waiting_for_category)
async def recipe_category(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    cat_map = {
        "n_b": "завтрак",
        "n_s": "гарнир",
        "n_m": "основное блюдо",
        "n_d": "салат"
    }
    category = cat_map.get(callback.data)
    if not category:
        await callback.message.edit_text("❌ Ошибка выбора категории.")
        return
    await state.update_data(category=category)
    if category in ["гарнир", "завтрак"]:
        await callback.message.edit_text("✍️ Введите способ приготовления:")
        await state.set_state(RecipeState.waiting_for_steps)
    else:
        await callback.message.edit_text("✍️ Введите ингредиенты (по одному на строку):")
        await state.set_state(RecipeState.waiting_for_ingredients)

@dp.message(RecipeState.waiting_for_ingredients)
async def recipe_ingredients(message: Message, state: FSMContext):
    ingredients = [i.strip() for i in message.text.strip().split("\n") if i.strip()]
    if not ingredients:
        await message.answer("❌ Список ингредиентов не может быть пустым.")
        return
    await state.update_data(ingredients=ingredients)
    await message.answer("✍️ Этапы приготовления (по одному на строку):")
    await state.set_state(RecipeState.waiting_for_steps)

@dp.message(RecipeState.waiting_for_steps)
async def recipe_steps(message: Message, state: FSMContext):
    steps = [s.strip() for s in message.text.strip().split("\n") if s.strip()]
    if not steps:
        await message.answer("❌ Этапы не могут быть пустыми.")
        return
    data = await state.get_data()
    name, category = data["name"], data["category"]
    ingredients = "\n".join(data.get("ingredients", []))
    steps_text = "\n".join(steps)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT OR REPLACE INTO recipes (name, category, ingredients, steps) VALUES (?, ?, ?, ?)",
                    (name, category, ingredients, steps_text))
        conn.commit()
        await message.answer(f"✅ Рецепт **{name}** добавлен!\n🔖 Категория: {category}", reply_markup=get_main_menu(), parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        conn.close()
    await state.clear()

# === ПОИСК ТОЛЬКО ПО ИНГРЕДИЕНТАМ ===
@dp.message(Command("search"))
async def search_recipes(message: Message, command: Command):
    if message.from_user.id != YOUR_USER_ID:
        return
    query = command.args
    if not query:
        await message.answer("✏️ Использование: `/search курица`", parse_mode="Markdown")
        return

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name, category, ingredients FROM recipes")
    rows = cur.fetchall()
    conn.close()

    results = []
    query_lower = query.lower()

    for name, category, ingredients in rows:
        if not ingredients or category in ["гарнир", "завтрак"]:
            continue
        if query_lower in (ingredients or "").lower():
            results.append((name, category))

    if not results:
        await message.answer(f"❌ Ничего не найдено в ингредиентах по запросу: *{query}*", parse_mode="Markdown")
        return

    MAX_RESULTS = 50
    results = results[:MAX_RESULTS]
    warning = f"\n\n⚠️ Показано {len(results)} из {len(results)}." if len(results) == MAX_RESULTS else ""

    keyboard = []
    for name, category in results:
        callback_data = f"r_{name[:60]}"
        disp_name = name if len(name) <= 50 else name[:47] + "..."
        keyboard.append([InlineKeyboardButton(text=f"🍽 {disp_name}", callback_data=callback_data)])
    keyboard.append([InlineKeyboardButton(text="⬅️ К категориям", callback_data="back_to_catalog")])

    await message.answer(
        f"🔍 Найдено {len(results)} рецептов с ингредиентом *{query}*:{warning}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.message(F.text & ~F.command)
async def handle_search_text(message: Message):
    if message.from_user.id != YOUR_USER_ID:
        return
    if message.text in ["📚 Каталог", "🧮 Калькулятор", "🥩 Белок", "➕ Добавить рецепт", "🔍 Поиск"]:
        return
    query = message.text.strip()
    if len(query) < 2:
        await message.answer("Введите запрос из 2 и более символов.")
        return

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name, category, ingredients FROM recipes")
    rows = cur.fetchall()
    conn.close()

    results = []
    query_lower = query.lower()

    for name, category, ingredients in rows:
        if not ingredients or category in ["гарнир", "завтрак"]:
            continue
        if query_lower in (ingredients or "").lower():
            results.append((name, category))

    if not results:
        await message.answer(f"❌ Ничего не найдено в ингредиентов по запросу: *{query}*", parse_mode="Markdown")
        return

    MAX_RESULTS = 50
    results = results[:MAX_RESULTS]
    warning = f"\n\n⚠️ Показано {len(results)} из {len(results)}." if len(results) == MAX_RESULTS else ""

    keyboard = []
    for name, category in results:
        callback_data = f"r_{name[:60]}"
        disp_name = name if len(name) <= 50 else name[:47] + "..."
        keyboard.append([InlineKeyboardButton(text=f"🍽 {disp_name}", callback_data=callback_data)])
    keyboard.append([InlineKeyboardButton(text="⬅️ К категориям", callback_data="back_to_catalog")])

    await message.answer(
        f"🔍 Найдено {len(results)} рецептов с ингредиентом *{query}*:{warning}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

# === РЕЗЕРВНАЯ КОПИЯ ===
@dp.message(Command("backup"))
async def send_db_backup(message: Message):
    if message.from_user.id != YOUR_USER_ID:
        return
    if os.path.exists(DB_FILE):
        await message.answer_document(document=FSInputFile(DB_FILE), caption="📦 Бэкап базы")
    else:
        await message.answer("❌ Файл базы не найден.")

@dp.message(F.document.file_name == "recipes.db")
async def handle_db_file(message: Message):
    if message.from_user.id != YOUR_USER_ID:
        return
    file_info = await bot.get_file(message.document.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    with open(DB_FILE, "wb") as f:
        f.write(downloaded_file.getvalue())
    await message.answer("✅ База данных обновлена!")

# === СБРОС БЕЛКА ===
async def reset_daily_protein():
    conn = get_db()
    conn.execute("UPDATE user_data SET value = '0' WHERE key = 'protein_today'")
    conn.commit()
    conn.close()

# === ЗАПУСК ===
async def main():
    init_db()
    scheduler.add_job(reset_daily_protein, 'cron', hour=0, minute=0, timezone="Europe/Moscow")
    scheduler.start()
    print("🟢 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
