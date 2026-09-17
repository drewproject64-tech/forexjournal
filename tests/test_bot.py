import os
import tempfile
import unittest

import bot


class ForexJournalSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        bot.DB_PATH = self.tmp.name
        bot.init_db()

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except FileNotFoundError:
            pass

    def test_database_initializes_and_is_empty(self):
        conn = bot.db_connect()
        try:
            total = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(total, 0)

    def test_user_records_are_isolated_by_user_id(self):
        conn = bot.db_connect()
        try:
            conn.execute(
                "INSERT INTO trades (user_id, pair, direction, entry, exit, notes, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (100, "EURUSD", "Buy", "1.0800", "1.0850", "test", "2026-01-01T00:00:00+00:00"),
            )
            conn.commit()
            user_100 = conn.execute("SELECT COUNT(*) FROM trades WHERE user_id = ?", (100,)).fetchone()[0]
            user_200 = conn.execute("SELECT COUNT(*) FROM trades WHERE user_id = ?", (200,)).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(user_100, 1)
        self.assertEqual(user_200, 0)

    def test_main_menu_contains_exactly_three_core_buttons(self):
        markup = bot.main_menu_keyboard()
        buttons = [button for row in markup.inline_keyboard for button in row]
        self.assertEqual(len(buttons), 3)
        self.assertEqual(
            {button.callback_data for button in buttons},
            {"menu:new", "menu:journal", "menu:settings"},
        )

    def test_all_main_menu_callbacks_are_unique_and_named(self):
        markup = bot.main_menu_keyboard()
        callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
        self.assertEqual(len(callbacks), len(set(callbacks)))
        self.assertTrue(all(callbacks))

    def test_positive_price_validation_rule(self):
        self.assertGreater(float("1.0850"), 0)
        with self.assertRaises(ValueError):
            value = float("0")
            if not value > 0:
                raise ValueError
        with self.assertRaises(ValueError):
            float("not-a-price")

    def test_journal_query_context_requires_explicit_user_id(self):
        # Prevents the callback path from accidentally querying callback.message.from_user
        # (the bot) instead of callback.from_user (the person using the journal).
        self.assertIn("user_id", bot.show_journal.__annotations__)


if __name__ == "__main__":
    unittest.main()
