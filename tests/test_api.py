import importlib.util
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    FastAPI = None
    TestClient = None

ROOT = Path(__file__).parents[1]


@unittest.skipUnless(FastAPI is not None, "FastAPI test dependencies are not installed")
class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = self._load(ROOT / "db.py", "api_db")
        self.db.DB_FILE = Path(self.tmp.name) / "db.sqlite"
        self.db.init_db()
        self.db.add_key("11111111-1111-4111-8111-111111111111")
        self.api = self._load(ROOT / "dashboard/plugin_api.py", "api_module")
        self.api._db.DB_FILE = self.db.DB_FILE
        self.api._db.init_db()
        app = FastAPI()
        app.include_router(self.api.router)
        self.client = TestClient(app)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _load(path, name):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_summary_includes_legacy_stats(self):
        self.db.bump_request("key:1")
        response = self.client.get("/summary")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["requests"], 1)

    def test_enable_disable_uses_key_id(self):
        self.assertEqual(self.client.post("/keys/1/disable").status_code, 200)
        self.assertFalse(self.db.key_by_id(1)["enabled"])
        self.assertEqual(self.client.post("/keys/1/enable").status_code, 200)
        self.assertTrue(self.db.key_by_id(1)["enabled"])

    def test_clear_events_removes_events(self):
        self.db.record_event("key_test", "success", 1, 200, 20)
        response = self.client.post("/events/clear")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["removed"], 1)
        self.assertEqual(self.db.recent_events(100), [])

    def test_event_pagination_is_bounded(self):
        self.assertEqual(self.client.get("/events?limit=1000").status_code, 422)
        self.assertEqual(self.client.get("/events?limit=10&offset=0").status_code, 200)


if __name__ == "__main__":
    unittest.main()
