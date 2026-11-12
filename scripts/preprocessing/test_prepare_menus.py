"""Regression checks for source fidelity, missing data and ambiguous aliases."""
import copy
import unittest

from prepare_menus import alias_index, normalize_one, process


class MenuPreprocessingTests(unittest.TestCase):
    def test_missing_caffeine_remains_unknown_and_raw_is_preserved(self):
        raw = {"id": "a", "name": "  보리   차  ", "temperature": None,
               "price": "2,000원", "description_raw": "원본\n설명",
               "caffeine_raw": None, "shots": None, "order_options": None,
               "quality_flags": ["caffeine_unit_g_review"]}
        original = copy.deepcopy(raw)
        item, doc = normalize_one(raw)
        self.assertEqual(raw, original)
        self.assertEqual(item["raw"], original)
        self.assertEqual(item["name"], "보리 차")
        self.assertEqual(item["price"], 2000)
        self.assertIsNone(item["caffeine"])
        self.assertIn("caffeine_missing", item["preprocess_flags"])
        self.assertNotIn("카페인 원문", doc["text"])
        self.assertEqual(doc["quality_flags"], ["caffeine_unit_g_review"])

    def test_shared_name_keeps_both_temperatures_and_iced_alias_is_specific(self):
        ice = {"id": "ice", "name": "아메리카노", "temperature": "ICE", "price": 2000}
        hot = {"id": "hot", "name": "아메리카노", "temperature": "HOT", "price": 2000}
        products, docs = process([ice, hot])
        idx = {row["alias"]: row for row in alias_index(products)}
        self.assertEqual([doc["menu_id"] for doc in docs], ["ice", "hot"])
        self.assertEqual(idx["아메리카노"]["candidate_menu_ids"], ["ice", "hot"])
        self.assertTrue(idx["아메리카노"]["ambiguous"])
        self.assertEqual(idx["아아"]["candidate_menu_ids"], ["ice"])
        self.assertEqual(idx["따뜻한 아메리카노"]["candidate_menu_ids"], ["hot"])

    def test_duplicate_ids_fail_instead_of_discarding_an_item(self):
        with self.assertRaisesRegex(ValueError, "중복 메뉴 ID"):
            process([{"id": "x", "name": "메뉴 A"}, {"id": "x", "name": "메뉴 B"}])

    def test_invalid_price_fails_instead_of_guessing(self):
        with self.assertRaisesRegex(ValueError, "변환할 수 없는 가격"):
            normalize_one({"id": "x", "name": "메뉴", "price": "2천원"})


if __name__ == "__main__":
    unittest.main()
