import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class MenuApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.menu_file = Path(self.tmp.name) / "menus.json"
        self.environment = patch.dict(os.environ, {"CAIFE_MENU_DATA_FILE": str(self.menu_file)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.client = TestClient(app)

    def test_local_records_are_returned_without_guessing_missing_values(self):
        source = [{
            "id": "demo-ice", "name": "라떼", "temperature": "ICE",
            "price": None, "shots": None, "caffeine_raw": "카페인 236.0g",
            "quality_flags": ["caffeine_unit_g_review"],
            "source_url": "https://example.com/menu", "collected_at": "2026-11-02T14:25:00+09:00",
        }]
        self.menu_file.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
        response = self.client.get("/api/menus")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], source)
        self.assertEqual(response.json()["collected_at"], source[0]["collected_at"])
        self.assertEqual(response.json()["source"], source[0]["source_url"])

    def test_missing_file_does_not_return_fallback_or_path(self):
        response = self.client.get("/api/menus")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(str(self.menu_file), response.text)
        self.assertNotIn("items", response.json())

    def test_invalid_json_or_invalid_records_fail_closed(self):
        for content in ("{", "[]", "{}", '[{"id": "123"}]'):
            with self.subTest(content=content):
                self.menu_file.write_text(content, encoding="utf-8")
                response = self.client.get("/api/menus")
                self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
