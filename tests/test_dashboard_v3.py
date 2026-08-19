import importlib.util
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

class DashboardV3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.db = load(ROOT / "db.py", "v3_db"); self.db.DB_FILE = Path(self.tmp.name) / "db.sqlite"; self.db.init_db()
    def tearDown(self): self.tmp.cleanup()
    def test_metadata_events_aggregation_and_settings(self):
        self.db.add_key("11111111-1111-4111-8111-111111111111"); key_id = self.db.list_keys()[0]["id"]
        self.assertTrue(self.db.set_key_enabled(key_id, False)); self.assertFalse(self.db.list_key_summaries()[0]["enabled"])
        self.db.record_event("search", "success", key_id, 200, 20, created_at=100); self.db.record_event("search", "rate_limited", key_id, 429, 30, created_at=101)
        summary = self.db.event_summary(0, 200); self.assertEqual(summary["requests"], 2); self.assertEqual(summary["rate_limits"], 1); self.assertEqual(summary["successful_requests"], 1)
        self.assertEqual(len(self.db.hourly_activity(0, 200)), 1); self.db.set_setting("retention_days", "7"); self.assertEqual(self.db.get_setting("retention_days"), "7")
    def test_key_summaries_do_not_expose_full_key(self):
        key = "11111111-1111-4111-8111-111111111111"
        self.db.add_key(key)
        summary = self.db.list_key_summaries()[0]
        self.assertNotIn("key", summary)
        self.assertEqual(summary["masked_key"], "11111111-111...1111")
    def test_event_pagination_is_bounded_and_pruning_keeps_recent_rows(self):
        for i in range(3): self.db.record_event("search", "success", created_at=int(time.time()) - i)
        self.assertEqual(len(self.db.recent_events(1000)), 3)
        removed = self.db.prune_events(365, 100); self.assertEqual(removed, 0)

if __name__ == "__main__": unittest.main()
