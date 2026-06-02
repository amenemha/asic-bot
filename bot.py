import os
import asyncio
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

import db
import rates
import calc

load_dotenv()
db.init()

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())

PREMIUM_ON = os.getenv("PREMIUM_ENABLED", "0") == "1"
FREE_LIMIT = int(os.getenv("FREE_LIMIT", "5"))

ASICS = {
    "s19": {"name": "🟦 Antminer S19", "th": 100, "w": 3250},
    "s21": {"name": "🟦 Antminer S21", "th": 200, "w": 3500},
    "m50": {"name": "🟧 Whatsminer M50", "th": 126, "w": 3276},
    "x3":  {"name": "🟨 Производитель 3", "th": 150, "w": 3300},
    "x4":  {"name": "🟩 Производитель 4", "th": 180, "w": 3400},
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
    rows = []
    for k, v in ASICS.items():
        rows.append([InlineKeyboardButton(
            text=f"{v['name']} — {v['th']} TH/s",
            callback_data=f"asic:{k}",
        )])
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
    
async def do_calc(m: types.Message, th: float, watts: float):
    u = db.get_user(m.from_user.id)
    kwh_price = u[3] if u and u[3] else 0
    asic_price = u[4] if u and u[4] else 0
    btc_v = await rates.btc_usd()
    rub_v = await rates.usd_rub()
    diff_v = await rates.difficulty()

    if not (btc_v and rub_v and diff_v):
        await m.answer("⚠️ Не удалось получить курсы. Попробуй позже.", reply_markup=main_kb())
        return

    r = calc.calc(th, watts, kwh_price, asic_price, btc_v, rub_v, diff_v)
    db.log_req(m.from_user.id, "calc", f"{th}/{watts}")

    text = (
        f"📊 Расчёт — {th:g} TH/s ⛏  {watts:g} Вт ⚡️\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Доход/сутки:\n"
        f"   {r['btc_day']:.8f} ₿\n"
        f"   ${r['usd_day']:.2f}  |  {r['rub_day']:,.0f} ₽\n"
        f"🔌 Электричество/сутки: {r['elec_day']:,.0f} ₽\n"
        f"📈 Чистая прибыль/сутки: {r['profit_day']:,.0f} ₽\n"
        f"🗓 В месяц: {r['month']:,.0f} ₽\n"
        f"📅 В год: {r['year']:,.0f} ₽"
    )
    if r["payback_days"]:
        text += f"\n⏳ Окупаемость: {r['payback_days']:,.0f} дней (~{r['payback_days']/30:.1f} мес) ✅"
    elif asic_price:
        text += "\n⚠️ Окупаемость: убыточно при текущих параметрах"
    else:
        text += "\nℹ️ Укажи цену ASIC в 🔧 Настройках для расчёта окупаемости"

    text = text.replace(",", " ")
    await m.answer(text, reply_markup=main_kb())


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
    lines = ["💹 Курс", "━━━━━━━━━"]
    lines.append(f"{btc:,.0f} BTC/USDT".replace(",", " ") if btc else "BTC/USDT — нет данных")
    lines.append(f"{rub:.2f} RUB/USDT" if rub else "RUB/USDT — нет данных")
    lines.append(f"{eth:,.0f} ETH/USDT".replace(",", " ") if eth else "ETH/USDT — нет данных")
    await m.answer("\n".join(lines))


@dp.message(F.text == "⚙️ Аппараты")
async def asics_info(m: types.Message):
    await m.answer("⛏ Список ASIC скоро появится.\nПока введи параметры вручную через 🧮 Рассчитать.")


@dp.message(F.text == "🔧 Настройки")
async def settings_menu(m: types.Message):
    u = db.get_user(m.from_user.id)
    kwh = f"{u[3]:g} ₽" if u and u[3] else "не задано"
    asicp = (f"{u[4]:,.0f} ₽".replace(",", " ")) if u and u[4] else "не задано"
    await m.answer(
        "🔧 Твои настройки\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"⚡️ Цена кВт·ч: {kwh}\n"
        f"🏷 Цена ASIC: {asicp}\n\n"
        "Что хочешь изменить?",
        reply_markup=settings_kb(),
    )@dp.callback_query(F.data == "set:kwh")
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
    await m.answer(f"✅ Сохранено: {v:g} ₽/кВт·ч", reply_markup=main_kb())


@dp.message(SettingsFSM.asic)
async def settings_set_asic(m: types.Message, state: FSMContext):
    try:
        v = float(m.text.replace(",", "."))
    except Exception:
        await m.answer("❌ Это не число. Пример: 250000")
        return
    db.set_asic_price(m.from_user.id, v)
    await state.clear()
    s = f"{v:,.0f} ₽".replace(",", " ")
    await m.answer(f"✅ Сохранено: {s}", reply_markup=main_kb())


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
    key = c.data.split(":", 1)[1]
    if key == "manual":
        await c.message.answer("Введи хешрейт в TH/s 💪\nНапример: 100, 200, 126")
        await state.set_state(Calc.th)
        await c.answer()
        return

    asic = ASICS.get(key)
    if not asic:
        await c.answer("Не нашёл этот ASIC", show_alert=True)
        return

    th = asic["th"]
    watts = asic["w"]
    u = db.get_user(c.from_user.id)
    if not u or not u[3]:
        await state.update_data(th=th, watts=watts)
        await c.message.answer(
            "⚡️ Сколько у тебя стоит 1 кВт·ч в ₽?\n"
            "Введи число (например: 4)\n\n"
            "Я запомню для всех будущих расчётов.\n"
            "Поменять можно в 🔧 Настройках."
        )
        await state.set_state(Calc.first_kwh)
        await c.answer()
        return

    await state.clear()
    await c.answer()
    await do_calc(c.message, th, watts)


@dp.message(Calc.th)
async def calc_th(m: types.Message, state: FSMContext):
    try:
        th = float(m.text.replace(",", "."))
    except Exception:
        await m.answer("❌ Это не число.\nПример: 100 (TH/s) 👇")
        return
    await state.update_data(th=th)
    await m.answer(
        "🔌 Шаг 2/2 — потребление 🔋\n\n"
        "Введи мощность ASIC в ваттах ⚡️\n"
        "Примеры:\n3250\n3500\n3276\n\n"
        "Просто отправь число 👇"
    )
    await state.set_state(Calc.watts)


@dp.message(Calc.watts)
async def calc_watts(m: types.Message, state: FSMContext):
    try:
        watts = float(m.text.replace(",", "."))
    except Exception:
        await m.answer("❌ Это не число.\nПример: 3500 (Вт) 👇")
        return
    data = await state.get_data()
    th = data.get("th")
    u = db.get_user(m.from_user.id)
    if not u or not u[3]:
        await state.update_data(watts=watts)
        await m.answer(
            "⚡️ Сколько у тебя стоит 1 кВт·ч в ₽?\n"
            "Введи число (например: 4)"
        )
        await state.set_state(Calc.first_kwh)
        return
    await state.clear()
    await do_calc(m, th, watts)


@dp.message(Calc.first_kwh)
async def first_kwh(m: types.Message, state: FSMContext):
    try:
        v = float(m.text.replace(",", "."))
    except Exception:
        await m.answer("❌ Это не число. Пример: 4")
        return
    db.set_kwh(m.from_user.id, v)
    data = await state.get_data()
    th = data.get("th")
    watts = data.get("watts")
    await state.clear()
    await m.answer(f"✅ Запомнил: {v:g} ₽/кВт·ч")
    if th and watts:
        await do_calc(m, th, watts)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
