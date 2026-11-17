import hashlib
import unittest

from workflow import WorkflowError, generate_for_human_review


class TestProvider:
    """테스트 전용 고정 응답: 실제 AI 생성 결과가 아니다."""
    model_identifier = "test-only"

    def __init__(self):
        self.calls = []
        self.responses = {
            "question_generator": {"question": "아메리카노 한 잔 주세요"},
            "action_generator": {
                "actions": [{"name": "ask_clarification", "arguments": {"field": "temperature"}}],
                "customer_reply": "아이스와 핫 중 어떤 걸로 드릴까요?",
                "source_ids": ["menu:americano"],
                "uncertainties": ["온도"],
            },
            "supervisor": {"verdict": "pass", "reason": "빠진 온도를 다시 질문했습니다."},
        }

    def complete(self, *, role, payload):
        self.calls.append((role, payload))
        return self.responses[role]


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.provider = TestProvider()
        self.facts = [{"id": "menu:americano", "text": "아메리카노는 HOT과 ICE가 있습니다."}]

    def run_workflow(self):
        return generate_for_human_review(self.provider, scenario="음료 주문", source_facts=self.facts)

    def test_roles_run_in_order_and_human_approval_is_pending(self):
        result = self.run_workflow()
        self.assertEqual([role for role, _ in self.provider.calls],
                         ["question_generator", "action_generator", "supervisor"])
        self.assertEqual(result["human_review"]["status"], "pending")
        self.assertEqual(result["provenance"]["origin"], "synthetic_ai")
        self.assertEqual(result["proposal"]["source_ids"], ["menu:americano"])
        self.assertEqual(self.provider.calls[1][1]["question"], result["question"])
        self.assertEqual(self.provider.calls[2][1]["proposal"], result["proposal"])

    def test_invalid_source_never_reaches_supervisor(self):
        self.provider.responses["action_generator"]["source_ids"] = ["invented"]
        with self.assertRaises(WorkflowError) as exc:
            self.run_workflow()
        self.assertEqual(exc.exception.stage, "action_generator")
        self.assertEqual(len(self.provider.calls), 2)

    def test_unknown_action_is_rejected(self):
        self.provider.responses["action_generator"]["actions"][0]["name"] = "charge_card"
        with self.assertRaises(WorkflowError):
            self.run_workflow()

    def test_invalid_review_is_rejected(self):
        self.provider.responses["supervisor"]["verdict"] = "approved"
        with self.assertRaises(WorkflowError) as exc:
            self.run_workflow()
        self.assertEqual(exc.exception.stage, "supervisor")

    def test_provider_failure_does_not_report_success(self):
        class Broken(TestProvider):
            def complete(self, *, role, payload):
                raise RuntimeError("sensitive-provider-message")
        with self.assertRaises(WorkflowError) as exc:
            generate_for_human_review(Broken(), scenario="주문", source_facts=[])
        self.assertNotIn("sensitive-provider-message", str(exc.exception))
        self.assertEqual(exc.exception.stage, "question_generator")

    def test_duplicate_source_ids_are_rejected_before_any_call(self):
        with self.assertRaises(WorkflowError):
            generate_for_human_review(self.provider, scenario="주문", source_facts=self.facts * 2)
        self.assertEqual(self.provider.calls, [])

    def test_add_to_cart_requires_positive_integer_quantity(self):
        for quantity in (-9, 0, True, 1.5, 100, None):
            with self.subTest(quantity=quantity):
                provider = TestProvider()
                provider.responses["action_generator"]["actions"] = [{
                    "name": "add_to_cart",
                    "arguments": {"menu_id": "menu:americano", "quantity": quantity},
                }]
                with self.assertRaises(WorkflowError) as exc:
                    generate_for_human_review(provider, scenario="주문", source_facts=self.facts)
                self.assertEqual(exc.exception.stage, "action_generator")
                self.assertEqual(len(provider.calls), 2)

    def test_add_to_cart_rejects_missing_or_uncited_menu(self):
        for menu_id, source_ids in (("invented", ["menu:americano"]), ("menu:americano", [])):
            with self.subTest(menu_id=menu_id, source_ids=source_ids):
                provider = TestProvider()
                provider.responses["action_generator"]["actions"] = [{
                    "name": "add_to_cart",
                    "arguments": {"menu_id": menu_id, "quantity": 1},
                }]
                provider.responses["action_generator"]["source_ids"] = source_ids
                with self.assertRaises(WorkflowError):
                    generate_for_human_review(provider, scenario="주문", source_facts=self.facts)
                self.assertEqual(len(provider.calls), 2)

    def test_valid_add_has_source_hash_and_still_awaits_person(self):
        self.provider.responses["action_generator"]["actions"] = [{
            "name": "add_to_cart",
            "arguments": {"menu_id": "menu:americano", "quantity": 2},
        }]
        result = self.run_workflow()
        self.assertEqual(result["human_review"]["status"], "pending")
        self.assertEqual(result["provenance"]["source_snapshots"], [{
            "id": "menu:americano",
            "text_sha256": hashlib.sha256(self.facts[0]["text"].encode("utf-8")).hexdigest(),
        }])

    def test_change_quantity_requires_cited_cart_item(self):
        self.provider.responses["action_generator"]["actions"] = [{
            "name": "change_cart_quantity",
            "arguments": {"cart_item_id": "cart:item-1", "quantity": 1},
        }]
        with self.assertRaises(WorkflowError):
            self.run_workflow()
        self.assertEqual(len(self.provider.calls), 2)


if __name__ == "__main__":
    unittest.main()

