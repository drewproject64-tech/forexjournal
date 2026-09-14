import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder


DB_PATH = os.getenv("DATABASE_PATH", "trades.db")
router = Router()


class TradeState(StatesGroup):
    pair = State()
    direction = State()
    entry = State()
    exit = State()
    notes = State()


def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db_connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            pair TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry TEXT NOT NULL,
            exit TEXT NOT NULL,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def home_keyboard():
    kb = ReplyKeyboardBuilder()
    kb.button(text="📝 New Trade")
    kb.button(text="📊 My Journal")
    kb.button(text="⚙️ Settings")
    kb.adjust(1, 1, 1)
    return kb.as_markup(resize_keyboard=True, is_persistent=True)


HOME_TEXT = (
    "<b>FOREX EXPERT TRADER</b>\n\n"
    "A simple personal trade journal for recording and reviewing your own trading activity.\n\n"
    "Record trade details, keep notes, and review your journal history.\n\n"
    "This bot is a record-keeping tool and does not provide trade signals, forecasts, investment advice, "
    "or guaranteed returns."
)


@router.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(HOME_TEXT, reply_markup=home_keyboard())


@router.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "<b>FOREX EXPERT TRADER</b>\n\n"
        "Use the three buttons below to manage your personal journal.\n\n"
        "📝 New Trade — record a completed or reviewed trade.\n"
        "📊 My Journal — view recent records and simple totals.\n"
        "⚙️ Settings — privacy and bot information."
    )


@router.message(F.text == "📝 New Trade")
async def new_trade(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(TradeState.pair)
    await message.answer(
        "<b>New Trade</b>\n\nStep 1/5\nSend the currency pair or instrument name.\nExample: <code>EURUSD</code>"
    )


@router.message(TradeState.pair)
async def trade_pair(message: Message, state: FSMContext):
    value = (message.text or "").strip()[:30]
    if not value:
        await message.answer("Please enter a pair or instrument name.")
        return
    await state.update_data(pair=value)
    await state.set_state(TradeState.direction)
    await message.answer("Step 2/5\nSend direction: <code>Buy</code> or <code>Sell</code>.")


@router.message(TradeState.direction)
async def trade_direction(message: Message, state: FSMContext):
    value = (message.text or "").strip().lower()
    if value not in {"buy", "sell"}:
        await message.answer("Please enter <code>Buy</code> or <code>Sell</code>.")
        return
    await state.update_data(direction=value.title())
    await state.set_state(TradeState.entry)
    await message.answer("Step 3/5\nSend the entry price.\nExample: <code>1.0850</code>")


@router.message(TradeState.entry)
async def trade_entry(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    try:
        float(value.replace(",", "."))
    except ValueError:
        await message.answer("Please enter a valid entry price.")
        return
    await state.update_data(entry=value)
    await state.set_state(TradeState.exit)
    await message.answer("Step 4/5\nSend the exit price.\nExample: <code>1.0900</code>")


@router.message(TradeState.exit)
async def trade_exit(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    try:
        float(value.replace(",", "."))
    except ValueError:
        await message.answer("Please enter a valid exit price.")
        return
    await state.update_data(exit=value)
    await state.set_state(TradeState.notes)
    await message.answer(
        "Step 5/5\nAdd a short note about the trade, or send <code>-</code> to skip."
    )


@router.message(TradeState.notes)
async def trade_notes(message: Message, state: FSMContext):
    data = await state.get_data()
    notes = (message.text or "").strip()
    if notes == "-":
        notes = ""
    notes = notes[:1000]

    conn = db_connect()
    conn.execute(
        "INSERT INTO trades (user_id, pair, direction, entry, exit, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            message.from_user.id,
            data["pair"],
            data["direction"],
            data["entry"],
            data["exit"],
            notes,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    await state.clear()

    await message.answer(
        "<b>Trade saved.</b>\n\n"
        f"Pair: <code>{data['pair']}</code>\n"
        f"Direction: <code>{data['direction']}</code>\n"
        f"Entry: <code>{data['entry']}</code>\n"
        f"Exit: <code>{data['exit']}</code>\n"
        f"Notes: {notes or 'None'}",
        reply_markup=home_keyboard(),
    )


@router.message(F.text == "📊 My Journal")
async def journal_handler(message: Message):
    conn = db_connect()
    rows = conn.execute(
        "SELECT * FROM trades WHERE user_id = ? ORDER BY id DESC LIMIT 10",
        (message.from_user.id,),
    ).fetchall()
    count = conn.execute(
        "SELECT COUNT(*) FROM trades WHERE user_id = ?",
        (message.from_user.id,),
    ).fetchone()[0]
    conn.close()

    if not rows:
        await message.answer(
            "<b>📊 My Journal</b>\n\nNo trades recorded yet. Tap <b>📝 New Trade</b> to add your first journal entry.",
            reply_markup=home_keyboard(),
        )
        return

    lines = [f"<b>📊 My Journal</b>\nTotal records: <b>{count}</b>\n"]
    for row in rows:
        lines.append(
            f"<b>#{row['id']} {row['pair']}</b> · {row['direction']}\n"
            f"Entry: <code>{row['entry']}</code> → Exit: <code>{row['exit']}</code>\n"
            f"Note: {row['notes'] or 'None'}\n"
        )
    await message.answer("\n".join(lines), reply_markup=home_keyboard())


@router.message(F.text == "⚙️ Settings")
async def settings_handler(message: Message):
    await message.answer(
        "<b>⚙️ Settings</b>\n\n"
        "<b>Privacy:</b> The bot stores journal entries linked to your Telegram user ID so they can be shown back to you. "
        "Do not enter passwords, broker credentials, payment information, or other sensitive account details.\n\n"
        "<b>About:</b> FOREX EXPERT TRADER is a personal record-keeping journal. "
        "It does not provide trade signals, personalized recommendations, market forecasts, or profit guarantees.",
        reply_markup=home_keyboard(),
    )


@router.message(Command("about"))
async def about_command(message: Message):
    await settings_handler(message)


@router.message(Command("privacy"))
async def privacy_command(message: Message):
    await settings_handler(message)


@router.message()
async def fallback(message: Message):
    await message.answer("Please use one of the three buttons below.", reply_markup=home_keyboard())


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN environment variable is required")

    init_db()
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    await bot.set_my_commands([
        ("start", "Open the journal"),
        ("help", "How the journal works"),
        ("about", "About the bot"),
        ("privacy", "Privacy information"),
    ])
    await bot.set_my_short_description(
        "Personal trade journal for recording and reviewing your own trading activity."
    )
    await bot.set_my_description(
        "FOREX EXPERT TRADER is a personal record-keeping journal for logging and reviewing trade history. "
        "It does not provide trade signals, forecasts, personalized investment advice, or guaranteed returns."
    )

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
