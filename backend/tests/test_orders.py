import json
import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


class OrderApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.menus = root / "menus.json"
        self.db = root / "orders" / "orders.sqlite3"
        self.menus.write_text(json.dumps([
            {"id": "coffee", "name": "커피", "price": 2000},
            {"id": "cake", "name": "케이크", "price": 3500},
            {"id": "unknown", "name": "가격 미확인", "price": None},
        ], ensure_ascii=False), encoding="utf-8")
        environment = patch.dict(os.environ, {
            "CAIFE_MENU_DATA_FILE": str(self.menus), "CAIFE_ORDER_DB_FILE": str(self.db)
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.client = TestClient(app)
        self.order = {"request_id": str(uuid4()), "dining": "포장",
                      "items": [{"menu_id": "coffee", "quantity": 2},
                                {"menu_id": "cake", "quantity": 1}],
                      "supplies": ["straw", "bag"], "payment_method": "card",
                      "expected_total": 7500}

    def count(self):
        if not self.db.exists():
            return 0
        with closing(sqlite3.connect(self.db)) as db:
            return db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]

    def test_order_is_saved_and_retry_returns_same_unpaid_record(self):
        first = self.client.post("/api/orders", json=self.order)
        self.assertEqual(first.status_code, 200, first.text)
        result = first.json()
        self.assertEqual(result["total"], 7500)
        self.assertEqual(result["items"][0]["unit_price"], 2000)
        self.assertEqual(result["payment_status"], "unpaid")
        self.assertEqual(result["status"], "recorded")
        self.assertEqual(result["dining"], "포장")
        self.assertEqual(result["supplies"], ["straw", "bag"])
        # The stored result is stable even if menu data subsequently changes.
        self.menus.unlink()
        second = self.client.post("/api/orders", json=self.order)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json(), result)
        self.assertEqual(self.count(), 1)

    def test_changed_retry_is_rejected(self):
        self.assertEqual(self.client.post("/api/orders", json=self.order).status_code, 200)
        changed = {**self.order, "dining": "매장 이용"}
        self.assertEqual(self.client.post("/api/orders", json=changed).status_code, 409)
        self.assertEqual(self.count(), 1)

    def test_simultaneous_retries_do_not_duplicate_an_order(self):
        def submit(_):
            with TestClient(app) as client:
                return client.post("/api/orders", json=self.order)

        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(submit, range(4)))
        self.assertEqual([response.status_code for response in responses], [200] * 4)
        self.assertEqual(len({response.json()["order_id"] for response in responses}), 1)
        self.assertEqual(self.count(), 1)

    def test_unknown_or_changed_prices_and_menu_are_not_saved(self):
        for change, status in [
            ({"expected_total": 1}, 409),
            ({"items": [{"menu_id": "unknown", "quantity": 1}]}, 400),
            ({"items": [{"menu_id": "missing", "quantity": 1}]}, 400),
            ({"items": [{"menu_id": "coffee", "quantity": 1, "price": 1}]}, 422),
        ]:
            with self.subTest(change=change):
                self.assertEqual(self.client.post("/api/orders", json={**self.order, **change}).status_code, status)
                self.assertEqual(self.count(), 0)

    def test_invalid_quantities_and_unverified_options_are_rejected(self):
        for item in [
            {"menu_id": "coffee", "quantity": 0},
            {"menu_id": "coffee", "quantity": -1},
            {"menu_id": "coffee", "quantity": True},
            {"menu_id": "coffee", "quantity": 1, "options": ["샷 추가"]},
        ]:
            with self.subTest(item=item):
                self.assertEqual(self.client.post("/api/orders", json={**self.order, "items": [item]}).status_code, 422)
        self.assertEqual(self.count(), 0)

    def test_invalid_id_supplies_or_duplicate_menu_is_rejected(self):
        for change in [
            {"request_id": "invalid"},
            {"supplies": ["self", "straw"]},
            {"items": [{"menu_id": "coffee", "quantity": 1}, {"menu_id": "coffee", "quantity": 1}]},
        ]:
            with self.subTest(change=change):
                self.assertEqual(self.client.post("/api/orders", json={**self.order, **change}).status_code, 422)
        self.assertEqual(self.count(), 0)

    def test_storage_failure_is_reported(self):
        with patch("app.main.sqlite3.connect", side_effect=sqlite3.OperationalError("private path")):
            response = self.client.post("/api/orders", json=self.order)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private path", response.text)


if __name__ == "__main__":
    unittest.main()
