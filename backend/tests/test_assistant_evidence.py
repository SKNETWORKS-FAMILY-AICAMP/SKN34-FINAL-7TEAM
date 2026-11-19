import unittest

from app.assistant_evidence import OrderEvidence, local_information_action
from app.assistant_turn import validate_plan
from app.openai_order import OrderPlan, OrderProviderError
from pydantic import ValidationError


class OrderPlanTests(unittest.TestCase):
    def test_rejects_nonexistent_options_and_checkout_before_add(self):
        cart = {"ice": {"option_groups": [{"id": "shot", "choices": [{"id": "shot_1"}, {"id": "shot_2"}]}]}}
        line = {"menu_id": "ice", "quantity": 1, "option_ids": ["shot_1", "shot_2"]}
        with self.assertRaises(OrderProviderError):
            validate_plan([{"type": "add_items", "items": [line]}], cart, {"전체"})
        line["option_ids"] = ["missing"]
        with self.assertRaises(OrderProviderError):
            validate_plan([{"type": "add_items", "items": [line]}], cart, {"전체"})
        with self.assertRaises(OrderProviderError):
            validate_plan([{"type": "open_checkout"}, {"type": "set_dining", "value": "포장"}], cart, {"전체"})

    def test_cannot_request_payment_execution(self):
        with self.assertRaises(ValidationError):
            OrderPlan.model_validate({"actions": [{"type": "charge_payment"}]})


class OrderEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.state = {"cart": [], "options": None, "pending": None, "rule_draft": None}
        self.repository = OrderEvidence(
            [
                {"id": "ice", "name": "아메리카노", "temperature": "ICE", "menu_facts": {
                    "nutrition": {"caffeine": {"status": "available", "raw": "카페인 180mg", "unit": "mg"}},
                    "serving_size": {"status": "available", "kind": "cup_capacity", "raw": "591ml"},
                }},
                {"id": "hot", "name": "아메리카노", "temperature": "HOT", "menu_facts": {
                    "nutrition": {"caffeine": {"status": "needs_review", "raw": "카페인 5g"}},
                }},
                {"id": "latte", "name": "카페라떼", "temperature": "HOT", "menu_facts": {
                    "allergens": {"status": "available", "items": ["우유"], "cross_contact": "unknown"},
                }},
            ],
            [{"alias": "아메리카노", "candidate_menu_ids": ["ice", "hot"]}],
            {"demo": True, "facts": [
                {"id": "restroom.location", "value": "정문 옆입니다."},
                {"id": "restroom.passcode", "value": "internal", "customer_visible": False},
                {"id": "service.warm_water", "value": "직원에게 문의해 주세요."},
                {"id": "hours.open", "value": "09:00"},
                {"id": "hours.close", "value": "21:00"},
            ]},
        )

    def turn(self, text, state=None, history=None):
        current = self.state if state is None else state
        evidence = self.repository.select(text, history or [], current)
        return evidence, local_information_action(text, evidence, ["전체", "디카페인"], current)

    def test_short_name_selects_ice_and_keeps_cup_volume_distinction(self):
        evidence, action = self.turn("아아 카페인이랑 용량 알려줘")
        self.assertEqual([item["menu_id"] for item in evidence["menus"]], ["ice"])
        self.assertIn("180mg", action["text"])
        self.assertIn("컵 용량", action["text"])

    def test_ambiguous_question_and_followup_use_status(self):
        question = "아메리카노 카페인 얼마예요?"
        evidence, action = self.turn(question)
        self.assertEqual(evidence["menu_status"], "ambiguous")
        self.assertEqual(action["type"], "ask")
        state = {**self.state, "pending": action}
        _, answer = self.turn("핫 아메리카노", state, [{"role": "customer", "text": question}])
        self.assertIn("확인하기 어려워요", answer["text"])
        self.assertNotIn("5g", answer["text"])

    def test_allergy_information_uses_selected_item_without_safety_claim(self):
        state = {**self.state, "options": {"menu_id": "latte"}}
        _, action = self.turn("이거 우유 들어갔어요?", state)
        self.assertIn("우유", action["text"])
        self.assertIn("교차 접촉", action["text"])

    def test_store_location_water_hours_and_unknown(self):
        for text, expected in [
            ("변소 어데고?", "정문 옆"),
            ("따뜻한 물 주세요", "직원에게 문의"),
            ("몇 시까지 열어요?", "21:00"),
            ("와이파이 비번은요?", "등록되어 있지"),
            ("화장실 비밀번호가 뭐예요?", "등록된 매장 안내가 없어요"),
        ]:
            with self.subTest(text=text):
                _, action = self.turn(text)
                self.assertIn(expected, action["text"])
                self.assertNotIn("internal", action["text"])

    def test_decaf_selection_and_mixed_order_are_separate(self):
        _, action = self.turn("카페인 적은 커피 추천해줘")
        self.assertEqual(action, {"type": "show_category", "category": "디카페인"})
        evidence, action = self.turn("아아 한 잔이랑 화장실 어디예요?")
        self.assertIsNone(action)
        self.assertEqual(evidence["store_topics"], ["restroom.location"])
        self.assertEqual(evidence["menus"][0]["menu_id"], "ice")
