import asyncio
import html
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, ErrorEvent, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder


APP_NAME = "FOREX EXPERT TRADER"
DB_PATH = os.getenv("DATABASE_PATH", "trades.db")
MAX_PAIR_LENGTH = 30
MAX_NOTES_LENGTH = 1000

router = Router()
logger = logging.getLogger(__name__)


class TradeState(StatesGroup):
    pair = State()
    direction = State()
    entry = State()
    exit = State()
    notes = State()


def db_connect() -> sqlite3.Connection:
    """Open the configured SQLite database and ensure its parent directory exists."""
    path = Path(DB_PATH)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = db_connect()
    try:
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
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades(user_id)"
        )
        conn.commit()
    finally:
        conn.close()


def main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 New Trade", callback_data="menu:new")
    builder.button(text="📊 My Journal", callback_data="menu:journal")
    builder.button(text="⚙️ Settings", callback_data="menu:settings")
    builder.adjust(1)
    return builder.as_markup()


def navigation_keyboard(*, retry: str | None = None):
    builder = InlineKeyboardBuilder()
    if retry:
        builder.button(text=retry, callback_data="menu:new")
    builder.button(text="🏠 Main Menu", callback_data="menu:home")
    builder.adjust(1)
    return builder.as_markup()


def settings_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Refresh", callback_data="menu:settings")
    builder.button(text="🏠 Main Menu", callback_data="menu:home")
    builder.adjust(1)
    return builder.as_markup()


HOME_TEXT = (
    f"<b>{APP_NAME}</b>\n\n"
    "A Telegram-native personal journal for recording and reviewing your own trade history.\n\n"
    "<b>Three functions:</b>\n"
    "📝 New Trade — save a trade with pair, direction, entry, exit and notes.\n"
    "📊 My Journal — review your records and basic journal totals.\n"
    "⚙️ Settings — view privacy and service information.\n\n"
    "Your entries are stored for your Telegram account. This bot does not provide trade signals, forecasts, "
    "personalized investment advice, or guaranteed returns."
)


async def show_home(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(HOME_TEXT, reply_markup=main_menu_keyboard())


async def show_journal(message: Message) -> None:
    try:
        conn = db_connect()
        try:
            rows = conn.execute(
                "SELECT id, pair, direction, entry, exit, notes, created_at "
                "FROM trades WHERE user_id = ? ORDER BY id DESC LIMIT 10",
                (message.from_user.id,),
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE user_id = ?",
                (message.from_user.id,),
            ).fetchone()[0]
            buys = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE user_id = ? AND direction = 'Buy'",
                (message.from_user.id,),
            ).fetchone()[0]
            sells = total - buys
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Database error while loading journal for user %s", message.from_user.id)
        await message.answer(
            "I couldn't load your journal right now. Please try again.",
            reply_markup=navigation_keyboard(retry="🔄 Try Again"),
        )
        return

    if not rows:
        await message.answer(
            "<b>📊 My Journal</b>\n\n"
            "You have no saved trades yet. Add your first trade to start building your journal.",
            reply_markup=navigation_keyboard(retry="📝 New Trade"),
        )
        return

    lines = [
        "<b>📊 My Journal</b>",
        f"Total records: <b>{total}</b> · Buy: <b>{buys}</b> · Sell: <b>{sells}</b>",
        "",
    ]
    for row in rows:
        pair = html.escape(row["pair"])
        direction = html.escape(row["direction"])
        entry = html.escape(row["entry"])
        exit_price = html.escape(row["exit"])
        notes = html.escape(row["notes"] or "None")
        lines.append(
            f"<b>#{row['id']} {pair}</b> · {direction}\n"
            f"Entry: <code>{entry}</code> → Exit: <code>{exit_price}</code>\n"
            f"Note: {notes}"
        )

    await message.answer(
        "\n".join(lines),
        reply_markup=navigation_keyboard(retry="📝 New Trade"),
    )


async def show_settings(message: Message) -> None:
    await message.answer(
        "<b>⚙️ Settings</b>\n\n"
        "<b>Privacy</b>\n"
        "The bot stores journal entries linked to your Telegram user ID so your records can be shown back to you. "
        "Do not enter passwords, broker credentials, payment information, or other sensitive account details.\n\n"
        "<b>About</b>\n"
        f"{APP_NAME} is a personal record-keeping journal. It does not provide trade signals, market forecasts, "
        "personalized investment recommendations, or profit guarantees.",
        reply_markup=settings_keyboard(),
    )


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    # Telegram Ads and normal deep links may append a start parameter. The bot
    # intentionally treats it as optional metadata and always opens the real product.
    await show_home(message, state)


@router.message(Command("help"))
async def help_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "<b>How to use this journal</b>\n\n"
        "📝 <b>New Trade</b>: enter a pair, Buy/Sell direction, entry price, exit price and an optional note.\n"
        "📊 <b>My Journal</b>: review your saved records and basic totals.\n"
        "⚙️ <b>Settings</b>: review privacy and service information.\n\n"
        "You can return to the main menu from any completed screen.",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "menu:home")
async def menu_home(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(HOME_TEXT, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "menu:new")
async def menu_new(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.set_state(TradeState.pair)
    await callback.message.edit_text(
        "<b>📝 New Trade</b>\n\n"
        "Step 1 of 5\nSend the currency pair or instrument name.\n"
        "Example: <code>EURUSD</code>",
        reply_markup=cancel_keyboard(),
    )


def cancel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✖️ Cancel", callback_data="trade:cancel")
    builder.button(text="🏠 Main Menu", callback_data="menu:home")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data == "menu:journal")
async def menu_journal(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await show_journal(callback.message)


@router.callback_query(F.data == "menu:settings")
async def menu_settings(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await show_settings(callback.message)


@router.callback_query(F.data == "trade:cancel")
async def cancel_trade(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Trade entry cancelled")
    await state.clear()
    await callback.message.edit_text(HOME_TEXT, reply_markup=main_menu_keyboard())


@router.message(TradeState.pair)
async def trade_pair(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    if not value:
        await message.answer("That input is empty. Please enter a pair or instrument name.", reply_markup=cancel_keyboard())
        return
    if len(value) > MAX_PAIR_LENGTH:
        await message.answer(f"Please keep the pair or instrument name to {MAX_PAIR_LENGTH} characters or fewer.", reply_markup=cancel_keyboard())
        return
    await state.update_data(pair=value)
    await state.set_state(TradeState.direction)
    await message.answer(
        "Step 2 of 5\nSend direction: <code>Buy</code> or <code>Sell</code>.",
        reply_markup=cancel_keyboard(),
    )


@router.message(TradeState.direction)
async def trade_direction(message: Message, state: FSMContext):
    value = (message.text or "").strip().lower()
    if value not in {"buy", "sell"}:
        await message.answer("Please enter <code>Buy</code> or <code>Sell</code>.", reply_markup=cancel_keyboard())
        return
    await state.update_data(direction=value.title())
    await state.set_state(TradeState.entry)
    await message.answer(
        "Step 3 of 5\nSend the entry price.\nExample: <code>1.0850</code>",
        reply_markup=cancel_keyboard(),
    )


@router.message(TradeState.entry)
async def trade_entry(message: Message, state: FSMContext):
    value = (message.text or "").strip().replace(",", ".")
    try:
        number = float(value)
        if not (number > 0):
            raise ValueError
    except ValueError:
        await message.answer("That entry price is not valid. Enter a positive number, for example <code>1.0850</code>.", reply_markup=cancel_keyboard())
        return
    await state.update_data(entry=value)
    await state.set_state(TradeState.exit)
    await message.answer(
        "Step 4 of 5\nSend the exit price.\nExample: <code>1.0900</code>",
        reply_markup=cancel_keyboard(),
    )


@router.message(TradeState.exit)
async def trade_exit(message: Message, state: FSMContext):
    value = (message.text or "").strip().replace(",", ".")
    try:
        number = float(value)
        if not (number > 0):
            raise ValueError
    except ValueError:
        await message.answer("That exit price is not valid. Enter a positive number, for example <code>1.0900</code>.", reply_markup=cancel_keyboard())
        return
    await state.update_data(exit=value)
    await state.set_state(TradeState.notes)
    await message.answer(
        "Step 5 of 5\nAdd a short note about the trade, or send <code>-</code> to skip.",
        reply_markup=cancel_keyboard(),
    )


@router.message(TradeState.notes)
async def trade_notes(message: Message, state: FSMContext):
    data = await state.get_data()
    notes = (message.text or "").strip()
    if notes == "-":
        notes = ""
    if len(notes) > MAX_NOTES_LENGTH:
        await message.answer(
            f"Please keep the note to {MAX_NOTES_LENGTH} characters or fewer.",
            reply_markup=cancel_keyboard(),
        )
        return

    try:
        conn = db_connect()
        try:
            conn.execute(
                "INSERT INTO trades (user_id, pair, direction, entry, exit, notes, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
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
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Database error while saving trade for user %s", message.from_user.id)
        await message.answer(
            "I couldn't save that trade because the journal is temporarily unavailable. Please try again.",
            reply_markup=navigation_keyboard(retry="📝 Try Again"),
        )
        return

    await state.clear()
    await message.answer(
        "<b>✅ Trade saved</b>\n\n"
        f"Pair: <code>{html.escape(data['pair'])}</code>\n"
        f"Direction: <code>{html.escape(data['direction'])}</code>\n"
        f"Entry: <code>{html.escape(data['entry'])}</code>\n"
        f"Exit: <code>{html.escape(data['exit'])}</code>\n"
        f"Notes: {html.escape(notes) if notes else 'None'}",
        reply_markup=navigation_keyboard(retry="📝 New Trade"),
    )


@router.message()
async def fallback(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "I didn't recognize that message. Please choose one of the three options below.",
        reply_markup=main_menu_keyboard(),
    )


@router.error()
async def error_handler(event: ErrorEvent):
    exception = event.exception
    if isinstance(exception, TelegramAPIError):
        logger.error("Telegram API error: %s", exception)
    else:
        logger.exception("Unhandled bot error", exc_info=exception)
    return True


async def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN environment variable is required")

    try:
        init_db()
        logger.info("Database initialized at %s", DB_PATH)
    except sqlite3.Error:
        logger.exception("Database initialization failed")
        raise

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    await bot.set_my_commands(
        [
            ("start", "Open the journal"),
            ("help", "How the journal works"),
        ]
    )
    await bot.set_my_short_description(
        "Personal Telegram-native journal for recording and reviewing trade history."
    )
    await bot.set_my_description(
        "FOREX EXPERT TRADER is a personal trade journal for recording and reviewing your own trade history. "
        "Use the bot to save trades, review journal records, and view privacy information. "
        "It does not provide trade signals, forecasts, personalized investment advice, or guaranteed returns."
    )

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("%s starting polling", APP_NAME)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger(__name__).info("Bot stopped")
