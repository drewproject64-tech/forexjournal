# FOREX EXPERT TRADER

A Telegram-native personal trade journal for recording and reviewing your own trade history.

## Three core functions

1. **New Trade** — records instrument, direction, entry, exit and an optional note with validation.
2. **My Journal** — shows saved records and basic totals for the current Telegram user.
3. **News & Updates** — displays original in-bot trading notes and product updates directly inside Telegram.

The main product experience stays inside Telegram. The bot does not require an external website, landing page, redirect, or external news destination for these functions.

## Commands

- `/start` — open the journal and main menu. Start parameters are accepted safely without redirecting anywhere.
- `/help` — explain the three functions and navigation.

## Configuration

Required: `BOT_TOKEN` — Telegram Bot API token.

Optional: `DATABASE_PATH` — SQLite database path, default `trades.db`.

Optional: `LOG_LEVEL` — Python logging level, default `INFO`.

Never commit a real bot token or other credentials.

## Local run

```bash
python -m venv .venv
pip install -r requirements.txt
python bot.py
```

## Docker

```bash
docker build -t forexjournal .
docker run --rm -e BOT_TOKEN="YOUR_TOKEN" forexjournal
```

## Render

`render.yaml` defines a Docker background worker and a persistent disk mounted at `/var/data`. The production database path is `/var/data/trades.db`. Set `BOT_TOKEN` as a secret environment variable.

## Data and QA

SQLite stores records against the Telegram user ID. Parameterized queries are used and user-entered text is HTML-escaped before being rendered in Telegram. Tests cover database initialization, user isolation, menu callback wiring, and price validation.

## Telegram Ads destination alignment

The advertised product should describe the same experience users receive after opening the bot: a functional Telegram-native trade journal with three clear functions. The bot's News & Updates section is local content rendered by the bot itself; it does not redirect users to external websites or external news pages.

Telegram's current Ads Guidelines require destinations to be functional, technically complete and active, and state that destinations must not be used only for redirecting to other landing pages. Verify the current official guidelines before submitting or changing an ad.
