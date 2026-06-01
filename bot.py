import asyncio, os, json
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import db, rates, calc

load_dotenv()
db.init()

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())

PREMIUM_ON = os.getenv("PREMIUM_ENABLED", "0") == "1"
FREE_LIMIT = int(os.getenv("FREE_LIMIT", "5"))

# Список ASIC (пока заглушки, потом заменишь реальные)
ASICS = {
    "s19":  {"name": "🟦 Antminer S19",   "th": 100, "w": 3250},
    "s21":  {"name": "🟦 Antminer S21",   "th": 200, "w": 3500},
    "m50":  {"name": "🟧 Whatsminer M50", "th": 126, "w": 3276},
    "x3":   {"name": "🟨 Производитель 3", "th": 150, "w": 3300},
    "x4":   {"name": "🟩 Производитель 4", "th": 180, "w": 3400},
}


def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧮 Рассчитать"), KeyboardButton(text="⚙️ Аппараты")],
            [KeyboardButton(text="💹 Курс"), KeyboardButton(text="🔧 Настройки")],
        ],
        resize_keyboard=True,
    )


def asics_kb():
    rows = [[InlineKeyboardButton(text=f"{v['name']} — {v['th']} TH/s", callback_data=f"asic:{k}")] for k, v in ASICS.items()]
    rows.append([InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="asic:manual")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ Изменить цену кВт·ч", callback_data="set:kwh")],
        [InlineKeyboardButton(text="🏷 Изменить цену ASIC", callback_data="set:asic")],
    ])


class Calc(StatesGroup):
    th = State()
    watts = State()
    first_kwh = State()


class SettingsFSM(StatesGroup):
    kwh = State()
    asic = State()


@dp.message(CommandStart())
async def start(m: types.Message):
    db.upsert_user(m.from_user.id, m.from_user.username, m.from_user.first_name)
    name = m.from_user.first_name or "друг"
    await m.answer(
        f"👋 Привет, {name}!\n\n"
        "Я помогу посчитать окупаемость ASIC ⛏\n"
        "Покажу курсы BTC и рубля, электричество и прибыль 💸\n"
        "Окупаемость и количество.\n\n"
        "Жми кнопку ниже 👇",
        reply_markup=main_kb(),
    )


@dp.message(F.text == "💹 Курс")
async def show_rates(m: types.Message):
    btc = await rates.btc_usd()
    eth = await rates.eth_usd()
    rub = await rates.usd_rub()
    text = "💹 *Курс*\n━━━━━━━━━\n"
    text += f"{btc:,.0f} BTC/USDT\n" if btc else "BTC/USDT — нет данных\n"
    text += f"{rub:.2f} RUB/USDT\n" if rub else "RUB/USDT — нет данных\n"
    text += f"{eth:,.0f} ETH/USDT" if eth else "ETH/USDT — нет данных"
    await m.answer(text, parse_mode="Markdown")


@dp.message(F.text == "⚙️ Аппараты")
async def asics_info(m: types.Message):
    await m.answer(
        "⛏ Список ASIC скоро появится.\n"
        "Пока введи параметры вручную через 🧮 Рассчитать."
    )


@dp.message(F.text == "🔧 Настройки")
async def settings_menu(m: types.Message):
    u = db.get_user(m.from_user.id)
    kwh = f"{u[3]} ₽" if u and u[3] else "не задано"
    asicp = f"{u[4]:,.0f} ₽".replace(",", " ") if u and u[4] else "не задано"
    await m.answer(
        "🔧 *Твои настройки*\n━━━━━━━━━━━━━━━━━━━\n"
        f"⚡️ Цена кВт·ч: *{kwh}*\n"
        f"🏷 Цена ASIC: *{asicp}*\n\n"
        "Что хочешь изменить?",
        reply_markup=settings_kb(),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data == "set:kwh")
async def cb_set_kwh(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer("⚡️ Введи цену кВт·ч в ₽ (например: 4)")
    await state.set_state(SettingsFSM.kwh)
    await c.answer()


@dp.callback_query(F.data == "set:asic")
async def cb_set_asic(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer("🏷 Введи цену ASIC в ₽ (например: 250000)")
    await state.set_state(SettingsFSM.asic)
    await c.answer()


@dp.message(SettingsFSM.kwh)
async def settings_set_kwh(m: types.Message, state: FSMContext):
    try:
        v = float(m.text.replace(",", "."))
    except Exception:
        await m.answer("❌ Это не число. Пример: 4")
        return
    db.set_kwh(m.from_user.id, v)
    await state.clear()
    await m.answer(f"✅ Сохранено: {v} ₽/кВт·ч", reply_markup=main_kb())


@dp.message(SettingsFSM.asic)
async def settings_set_asic(m: types.Message, state: FSMContext):
    try:
        v = float(m.text.replace(",", "."))
    except Exception:
        await m.answer("❌ Это не число. Пример: 250000")
        return
    db.set_asic_price(m.from_user.id, v)
    await state.clear()
    await m.answer(f"✅ Сохранено: {v:,.0f} ₽".replace(",", " "), reply_markup=main_kb())


@dp.message(F.text == "🧮 Рассчитать")
async def calc_start(m: types.Message, state: FSMContext):
    if PREMIUM_ON:
        u = db.get_user(m.from_user.id)
        if (not u or not u[5]) and db.count_today(m.from_user.id) >= FREE_LIMIT:
            await m.answer("🚫 Лимит 5 расчётов в сутки исчерпан.\nПодключи Premium ✨ — расчёты без ограничений.")
            return
    await m.answer(
        "⚡️ Шаг 1/2 — хешрейт ⛏\n\n"
        "Выбери ASIC из списка ниже 👇\n"
        "или просто введи число (TH/s) вручную",
        reply_markup=asics_kb(),
    )
    await state.set_state(Calc.th)


@dp.callback_query(F.data.startswith("asic:"))
async def cb_asic(c: types.CallbackQuery, state: FSMContext):
    key = c.data.
