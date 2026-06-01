import asyncio, os, json
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
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


def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧮 Рассчитать"), KeyboardButton(text="⚙️ Аппараты")],
            [KeyboardButton(text="💱 Курсы"), KeyboardButton(text="🔧 Настройки")],
        ],
        resize_keyboard=True,
    )


class Calc(StatesGroup):
    th = State()
    watts = State()


class Settings(StatesGroup):
    kwh = State()
    asic = State()


@dp.message(CommandStart())
async def start(m: types.Message):
    db.upsert_user(m.from_user.id, m.from_user.username, m.from_user.first_name)
    await m.answer(
        "Привет! Я считаю окупаемость ASIC.\nВыбери действие:",
        reply_markup=main_kb(),
    )


@dp.message(F.text == "💱 Курсы")
async def show_rates(m: types.Message):
    btc = await rates.btc_usd()
    rub = await rates.usd_rub()
    diff = await rates.difficulty()
    text = "Курсы и сеть BTC:\n"
    text += f"BTC: ${btc:,.0f}\n" if btc else "BTC: нет данных\n"
    text += f"USD→RUB: {rub:.2f}\n" if rub else "USD→RUB: нет данных\n"
    text += f"Сложность: {diff:,.0f}" if diff else "Сложность: нет данных"
    await m.answer(text)


@dp.message(F.text == "🔧 Настройки")
async def settings_menu(m: types.Message, state: FSMContext):
    u = db.get_user(m.from_user.id)
    kwh = u[3] if u and u[3] else "не задано"
    asicp = u[4] if u and u[4] else "не задано"
    await m.answer(
        f"Цена кВт·ч: {kwh}\nЦена ASIC: {asicp}\n\nВведи цену кВт·ч в ₽ (или /skip):"
    )
    await state.set_state(Settings.kwh)


@dp.message(Settings.kwh)
async def set_kwh(m: types.Message, state: FSMContext):
    if m.text != "/skip":
        try:
            db.set_kwh(m.from_user.id, float(m.text.replace(",", ".")))
        except Exception:
            await m.answer("Введи число.")
            return
    await m.answer("Введи цену ASIC в ₽ (или /skip):")
    await state.set_state(Settings.asic)


@dp.message(Settings.asic)
async def set_asic(m: types.Message, state: FSMContext):
    if m.text != "/skip":
        try:
            db.set_asic_price(m.from_user.id, float(m.text.replace(",", ".")))
        except Exception:
            await m.answer("Введи число.")
            return
    await state.clear()
    await m.answer("Сохранено.", reply_markup=main_kb())


@dp.message(F.text == "⚙️ Аппараты")
async def asics(m: types.Message):
    await m.answer("Список ASIC появится позже. Пока введи параметры вручную.")


@dp.message(F.text == "🧮 Рассчитать")
async def calc_start(m: types.Message, state: FSMContext):
    if PREMIUM_ON:
        u = db.get_user(m.from_user.id)
        if (not u or not u[5]) and db.count_today(m.from_user.id) >= FREE_LIMIT:
            await m.answer(f"Лимит {FREE_LIMIT}/день. Включи Premium позже.")
            return
    await m.answer("Введи хешрейт в TH/s:")
    await state.set_state(Calc.th)


@dp.message(Calc.th)
async def calc_th(m: types.Message, state: FSMContext):
    try:
        th = float(m.text.replace(",", "."))
    except Exception:
        await m.answer("Введи число.")
        return
    await state.update_data(th=th)
    await m.answer("Введи потребление в Вт:")
    await state.set_state(Calc.watts)


@dp.message(Calc.watts)
async def calc_watts(m: types.Message, state: FSMContext):
    try:
        watts = float(m.text.replace(",", "."))
    except Exception:
        await m.answer("Введи число.")
        return
    data = await state.get_data()
    th = data["th"]
    await state.clear()

    u = db.get_user(m.from_user.id)
    kwh_price = u[3] if u and u[3] else 0
    asic_price = u[4] if u and u[4] else 0

    btc_v = await rates.btc_usd()
    rub_v = await rates.usd_rub()
    diff_v = await rates.difficulty()

    if not (btc_v and rub_v and diff_v):
        await m.answer("Не удалось получить курсы. Попробуй позже.", reply_markup=main_kb())
        return

    r = calc.calc(th, watts, kwh_price, asic_price, btc_v, rub_v, diff_v)
    db.log_req(m.from_user.id, "calc", json.dumps({"th": th, "watts": watts}))

    text = (
        f"📊 Расчёт ({th} TH/s, {watts} Вт)\n\n"
        f"Доход/сутки: {r['btc_day']:.8f} BTC | ${r['usd_day']:.2f} | {r['rub_day']:.0f} ₽\n"
        f"Электричество/сутки: {r['elec_day']:.0f} ₽\n"
        f"Чистая прибыль/сутки: {r['profit_day']:.0f} ₽\n"
        f"В месяц: {r['month']:.0f} ₽\n"
        f"В год: {r['year']:.0f} ₽\n"
    )
    if r["payback_days"]:
        text += f"\nОкупаемость: {r['payback_days']:.0f} дней (~{r['payback_days']/30:.1f} мес)"
    elif asic_price:
        text += "\nОкупаемость: убыточно при текущих параметрах"
    else:
        text += "\n(укажи цену ASIC в Настройках для расчёта окупаемости)"

    await m.answer(text, reply_markup=main_kb())


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
