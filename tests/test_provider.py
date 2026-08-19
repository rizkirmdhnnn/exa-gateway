import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


DB_PATH = Path(__file__).parents[1] / "db.py"
PROVIDER_PATH = Path(__file__).parents[1] / "provider.py"


class ProviderTests(unittest.TestCase):
    def test_round_robin_uses_stable_key_ids(self):
        db_spec = importlib.util.spec_from_file_location("exa_gateway_provider_db", DB_PATH)
        db = importlib.util.module_from_spec(db_spec)
        db_spec.loader.exec_module(db)
        db.list_keys = lambda: [
            {"id": 7, "key": "first"},
            {"id": 9, "key": "second"},
        ]
        import sys
        import types
        package = types.ModuleType("exa_gateway_test_pkg")
        package.__path__ = [str(PROVIDER_PATH.parent)]
        sys.modules["exa_gateway_test_pkg"] = package
        sys.modules["exa_gateway_test_pkg.db"] = db
        provider_spec = importlib.util.spec_from_file_location(
            "exa_gateway_test_pkg.provider", PROVIDER_PATH)
        provider = importlib.util.module_from_spec(provider_spec)
        with patch.dict("sys.modules", {"agent.web_search_provider": type("M", (), {"WebSearchProvider": object})}):
            sys.modules[provider_spec.name] = provider
            provider_spec.loader.exec_module(provider)
        provider.RR_INDEX = 0
        sys.modules.pop("exa_gateway_test_pkg.provider", None)
        sys.modules.pop("exa_gateway_test_pkg.db", None)
        sys.modules.pop("exa_gateway_test_pkg", None)
        self.assertEqual(provider._next_key(), ("first", "key:7"))
        self.assertEqual(provider._next_key(), ("second", "key:9"))
        self.assertEqual(provider._next_key(), ("first", "key:7"))


if __name__ == "__main__":
    unittest.main()
