"""Regression checks for source fidelity, missing data and ambiguous aliases."""
import copy
import unittest

from prepare_menus import alias_index, normalize_one, process, parse_nutrient, parse_serving_size, parse_allergens


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

    def test_cup_capacity_is_not_inferred_to_be_beverage_amount(self):
        size = parse_serving_size("컵용량 : 591ml")
        self.assertEqual(size["kind"], "cup_capacity")
        self.assertEqual((size["value"], size["unit"], size["basis"]), (591, "ml", None))
        one = parse_serving_size("One size")
        self.assertEqual((one["status"], one["value"]), ("review_required", None))
        weight = parse_serving_size("50g")
        self.assertEqual((weight["kind"], weight["value"], weight["unit"]), ("listed_quantity", 50, "g"))

    def test_explicit_zero_is_not_a_missing_value_and_basis_is_not_invented(self):
        sugar = parse_nutrient("당류 0.0g", "당류", "g")
        self.assertEqual((sugar["status"], sugar["value"], sugar["unit"]), ("available", 0, "g"))
        self.assertIsNone(sugar["basis"])
        cal = parse_nutrient("1회 제공량 1,679kcal", "1회 제공량", "kcal")
        self.assertEqual((cal["value"], cal["unit"], cal["basis"]), (1679, "kcal", "1회 제공량"))

    def test_unusual_unit_and_percent_are_not_silently_corrected(self):
        wrong = parse_nutrient("카페인 236.0g", "카페인", "mg", ["caffeine_unit_g_review"])
        self.assertEqual((wrong["status"], wrong["value"], wrong["unit"]), ("review_required", None, None))
        self.assertEqual((wrong["source_value"], wrong["source_unit"]), (236, "g"))
        missing = parse_nutrient(None, "카페인", "mg")
        self.assertEqual(missing["status"], "missing")
        odd = parse_nutrient("1회 제공량 215kcl", "1회 제공량", "kcal")
        self.assertEqual((odd["status"], odd["value"], odd["source_unit"]), ("review_required", None, "kcl"))
        percent = parse_nutrient("카페인 커피분말 5%", "카페인", "mg")
        self.assertEqual(percent["status"], "review_required")

    def test_allergen_blank_and_caffeine_warning_are_unknown_not_none(self):
        for raw in ("알레르기 성분 :", "알레르기 성분 : 고카페인 함유"):
            info = parse_allergens(raw)
            self.assertEqual(info["status"], "missing")
            self.assertEqual(info["items"], [])
            self.assertEqual(info["cross_contact"], "unknown")
        self.assertEqual(parse_allergens("알레르기 성분 : 고카페인 함유")["warnings"], ["고카페인 함유"])

    def test_allergen_parenthetical_comma_and_warning_are_preserved(self):
        info = parse_allergens("알레르기 성분 : 알류,우유,대두,밀,조개류(굴,바지락) 고카페인 함유")
        self.assertEqual(info["status"], "available")
        self.assertIn("조개류(굴,바지락)", info["items"])
        self.assertNotIn("고카페인 함유", info["items"])
        self.assertEqual(info["warnings"], ["고카페인 함유"])

    def test_nutrition_or_ingredient_conditions_require_review(self):
        raw = {"id": "x", "name": "라떼", "price": 2000,
               "description_raw": "원료 전환 기간에는 영양정보가 매장에 따라 다를 수 있습니다.",
               "calories_raw": "1회 제공량 200kcal", "allergen_raw": "알레르기 성분 : 우유"}
        item, doc = normalize_one(raw)
        self.assertTrue(item["menu_facts"]["description_conditions_review"])
        self.assertIn("description_conditions_review", doc["preprocess_flags"])
        self.assertIn("열량 원문", doc["text"])
        self.assertEqual(item["menu_facts"]["nutrition"]["calories"]["status"], "review_required")
        self.assertIsNone(item["menu_facts"]["nutrition"]["calories"]["value"])
        self.assertEqual(item["menu_facts"]["nutrition"]["calories"]["source_value"], 200)
        self.assertEqual(item["menu_facts"]["allergens"]["status"], "review_required")


if __name__ == "__main__":
    unittest.main()
