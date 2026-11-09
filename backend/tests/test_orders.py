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
        ]:
            with self.subTest(item=item):
                self.assertEqual(self.client.post("/api/orders", json={**self.order, "items": [item]}).status_code, 422)
        self.assertEqual(self.count(), 0)

    def test_ice_americano_options_are_priced_and_saved(self):
        items = json.loads(self.menus.read_text(encoding="utf-8"))
        items += [{"id": "ice-americano", "name": "아메리카노", "temperature": "ICE", "price": 2000},
                  {"id": "hot-americano", "name": "아메리카노", "temperature": "HOT", "price": 2000}]
        self.menus.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        menus = self.client.get("/api/menus").json()["items"]
        iced = next(item for item in menus if item["id"] == "ice-americano")
        hot = next(item for item in menus if item["id"] == "hot-americano")
        self.assertEqual(len(iced["option_groups"]), 4)
        self.assertNotIn("option_groups", hot)
        request = {**self.order,
                   "items": [{"menu_id": "ice-americano", "quantity": 2,
                              "options": ["shot_1", "stevia"]},
                             {"menu_id": "ice-americano", "quantity": 1, "options": []}],
                   "expected_total": 8400}
        response = self.client.post("/api/orders", json=request)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["total"], 8400)
        self.assertEqual(result["items"][0]["base_price"], 2000)
        self.assertEqual(result["items"][0]["unit_price"], 3200)
        self.assertEqual(result["items"][0]["line_total"], 6400)
        self.assertEqual([x["id"] for x in result["items"][0]["selected_options"]], ["shot_1", "stevia"])
        self.assertEqual(self.count(), 1)

    def test_invalid_options_conflicting_group_and_false_total_are_rejected(self):
        items = json.loads(self.menus.read_text(encoding="utf-8"))
        items.append({"id": "ice-americano", "name": "아메리카노", "temperature": "ICE", "price": 2000})
        self.menus.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        for menu_id, options, total, status in [
            ("coffee", ["shot_1"], 2600, 400),
            ("ice-americano", ["shot_1", "shot_2"], 3800, 400),
            ("ice-americano", ["stevia", "condensed_milk"], 3300, 400),
            ("ice-americano", ["stevia", "stevia"], 3200, 400),
            ("ice-americano", ["shot_1"], 2000, 409),
        ]:
            with self.subTest(menu=menu_id, options=options):
                request = {**self.order, "items": [{"menu_id": menu_id, "quantity": 1, "options": options}],
                           "expected_total": total}
                self.assertEqual(self.client.post("/api/orders", json=request).status_code, status)
                self.assertEqual(self.count(), 0)

    def test_unverified_option_definitions_from_menu_file_are_not_used(self):
        items = json.loads(self.menus.read_text(encoding="utf-8"))
        items[0]["option_groups"] = [{"id": "fake", "choices": [{"id": "fake", "price": -1000}]}]
        self.menus.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        menu = self.client.get("/api/menus").json()["items"][0]
        self.assertNotIn("option_groups", menu)
        request = {**self.order, "items": [{"menu_id": "coffee", "quantity": 1, "options": ["fake"]}],
                   "expected_total": 1000}
        self.assertEqual(self.client.post("/api/orders", json=request).status_code, 400)
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
