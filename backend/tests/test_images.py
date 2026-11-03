import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app


class MenuImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.images = self.root / "images"
        self.images.mkdir()
        self.menu_id = "0123456789abcdef0123"
        self.env = patch.dict(os.environ, {"CAIFE_MENU_DATA_FILE": str(self.root / "menus.json")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client = TestClient(app)

    def test_serves_only_indexed_local_image(self):
        filename = self.menu_id + ".png"
        (self.images / "index.json").write_text(json.dumps({self.menu_id: filename}), encoding="utf-8")
        (self.images / filename).write_bytes(b"\x89PNG\r\n\x1a\nplaceholder")
        result = self.client.get("/api/menu-images/" + self.menu_id)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers["content-type"], "image/png")
        self.assertEqual(result.headers["x-content-type-options"], "nosniff")

    def test_missing_and_unindexed_images_return_404(self):
        self.assertEqual(self.client.get("/api/menu-images/" + self.menu_id).status_code, 404)
        (self.images / "index.json").write_text("{}", encoding="utf-8")
        (self.images / (self.menu_id + ".png")).write_bytes(b"test")
        self.assertEqual(self.client.get("/api/menu-images/" + self.menu_id).status_code, 404)

    def test_invalid_ids_and_index_path_are_rejected(self):
        (self.images / "index.json").write_text(json.dumps({self.menu_id: "../private.png"}), encoding="utf-8")
        self.assertEqual(self.client.get("/api/menu-images/" + self.menu_id).status_code, 404)
        self.assertEqual(self.client.get("/api/menu-images/not-a-menu-id").status_code, 404)
        (self.images / "index.json").write_text("{", encoding="utf-8")
        self.assertEqual(self.client.get("/api/menu-images/" + self.menu_id).status_code, 404)


if __name__ == "__main__":
    unittest.main()
