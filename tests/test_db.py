import importlib.util
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path


MODULE = Path(__file__).parents[1] / "db.py"


def load_db(path):
    spec = importlib.util.spec_from_file_location("exa_gateway_test_db", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DB_FILE = Path(path)
    return module


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = load_db(Path(self.tmp.name) / "data" / "exa.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_is_idempotent_and_sets_private_mode(self):
        key = "11111111-1111-4111-8111-111111111111"
        self.db.add_key(key)
        self.db.add_key(key)
        self.assertEqual(len(self.db.list_keys()), 1)
        self.assertEqual(self.db.DB_FILE.stat().st_mode & 0o777, 0o600)

    def test_delete_uses_stable_id(self):
        self.db.add_key("11111111-1111-4111-8111-111111111111")
        self.db.add_key("22222222-2222-4222-8222-222222222222")
        rows = self.db.list_keys()
        self.assertTrue(self.db.remove_key_id(rows[1]["id"]))
        self.assertEqual([r["key"] for r in self.db.list_keys()], [rows[0]["key"]])
        self.assertFalse(self.db.remove_key_id(rows[1]["id"]))

    def test_old_stats_are_mapped_to_current_key_ids(self):
        key = "11111111-1111-4111-8111-111111111111"
        self.db.add_key(key)
        con = sqlite3.connect(self.db.DB_FILE)
        con.execute(
            "INSERT INTO stats(account_id, requests, errors, last_error, last_used) VALUES (?, ?, ?, ?, ?)",
            ("0:" + key[:12], 4, 1, "old error", 10),
        )
        con.commit()
        con.close()
        stats = self.db.get_stats()
        row = stats[f"key:{self.db.list_keys()[0]['id']}"]
        self.assertEqual(row["requests"], 4)
        self.assertEqual(row["errors"], 1)
        self.assertEqual(row["last_error"], "old error")


if __name__ == "__main__":
    unittest.main()
