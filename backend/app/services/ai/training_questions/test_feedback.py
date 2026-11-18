from copy import deepcopy
import unittest

from workflow import WorkflowError, revise_actions_from_feedback


class FeedbackProvider:
    def __init__(self, plan):
        self.calls = []
        self.plan = plan

    def complete(self, *, role, payload):
        self.calls.append((role, payload))
        if "cases" in payload:
            return self.plan
        if role == "action_generator":
            return {
                "actions": [{
                    "name": "add_to_cart",
                    "arguments": {"menu_id": "iced-americano", "quantity": 2},
                }],
                "customer_reply": "아이스 아메리카노 두 잔 담았어요. 더 필요한 거 있으세요?",
                "source_ids": ["iced-americano"],
                "uncertainties": [],
            }
        return {"verdict": "pass", "reason": "필요한 메뉴와 수량을 바로 담는 제안입니다."}


class FeedbackTest(unittest.TestCase):
    def setUp(self):
        self.feedback = "아아 두 잔이라고 했으면 온도는 다시 묻지 말고 두 잔을 담아."
        questions = {
            "explicit": "아아 두 잔 주세요",
            "ambiguous": "아메리카노 두 잔 주세요",
            "approved": "아아 한 잔 주세요",
        }
        self.cases = {
            case_id: {
                "report": {
                    "scenario": "음료 주문",
                    "question": question,
                    "proposal": {
                        "actions": [{"name": "ask_clarification", "arguments": {"field": "temperature"}}],
                        "customer_reply": "아이스로 드릴까요?",
                        "source_ids": [],
                        "uncertainties": ["온도"],
                    },
                    "human_review": {"status": "approved" if case_id == "approved" else "pending"},
                },
                "source_facts": [{"id": "iced-americano", "text": "'아아'는 아이스 아메리카노입니다."}],
            }
            for case_id, question in questions.items()
        }

    def revise(self, provider):
        return revise_actions_from_feedback(provider, cases=self.cases, feedback=self.feedback)

    def test_revises_and_reviews_only_the_selected_case(self):
        provider = FeedbackProvider({
            "targets": [{"case_id": "explicit", "instruction": "아이스 아메리카노 두 잔을 담으세요."}],
        })
        originals = deepcopy(self.cases)
        result = self.revise(provider)
        self.assertEqual(self.cases, originals)
        self.assertEqual(result["status"], "revised")
        self.assertEqual([change["case_id"] for change in result["changes"]], ["explicit"])
        change = result["changes"][0]
        self.assertEqual(change["before"], originals["explicit"]["report"]["proposal"])
        self.assertEqual(change["after"]["actions"], [{
            "name": "add_to_cart",
            "arguments": {"menu_id": "iced-americano", "quantity": 2},
        }])
        self.assertEqual(change["human_review"]["status"], "pending")
        self.assertEqual(change["ai_review"]["verdict"], "pass")
        self.assertEqual([role for role, _ in provider.calls], ["supervisor", "action_generator", "supervisor"])
        selection, revision, review = [payload for _, payload in provider.calls]
        self.assertEqual(selection["feedback"], self.feedback)
        self.assertEqual([case["case_id"] for case in selection["cases"]], ["explicit", "ambiguous"])
        self.assertEqual(revision["revision"]["before"], change["before"])
        self.assertEqual(review["proposal"], change["after"])

    def test_asks_for_clarification_without_regenerating_actions(self):
        provider = FeedbackProvider({"targets": [], "clarification": "어떤 안내를 줄일까요?"})
        self.assertEqual(self.revise(provider), {
            "status": "needs_clarification", "clarification": "어떤 안내를 줄일까요?", "changes": [],
        })
        self.assertEqual(len(provider.calls), 1)

    def test_rejects_invalid_targets_before_regenerating_any_action(self):
        for invalid in ("approved", "unknown", "explicit"):
            with self.subTest(case_id=invalid):
                provider = FeedbackProvider({
                    "targets": [
                        {"case_id": "explicit", "instruction": "바로 담으세요."},
                        {"case_id": invalid, "instruction": "안내 문구도 바꾸세요."},
                    ],
                })
                with self.assertRaises(WorkflowError) as error:
                    self.revise(provider)
                self.assertEqual(error.exception.stage, "feedback")
                self.assertEqual(len(provider.calls), 1)


if __name__ == "__main__":
    unittest.main()
