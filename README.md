# FOREX EXPERT TRADER

A Telegram-native personal trade journal for recording and reviewing your own trade history.

## Three core functions

1. **New Trade** — records instrument, direction, entry, exit and an optional note with validation.
2. **My Journal** — shows saved records and basic totals for the current Telegram user.
3. **Settings** — explains storage, privacy and what the bot does not provide.

The bot is intentionally small: the main menu exposes only these three product functions.

## Commands

- `/start` — open the journal and main menu. Telegram start parameters are accepted safely.
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

SQLite stores records against the Telegram user ID. Parameterized queries are used and user-entered text is HTML-escaped before being rendered in Telegram. Smoke tests cover database initialization, user isolation, menu callback wiring, and price validation.

## Telegram Ads destination alignment

The profile description, `/start`, menu and destination are designed to describe the same in-Telegram product. The bot does not use an external redirect as its core experience. Telegram's current Ads Guidelines require destinations to be functional, technically complete and active, with bots responding properly on mobile and desktop; they also prohibit mostly noninteractive redirect bots. Verify the current official policy before submitting an ad.
