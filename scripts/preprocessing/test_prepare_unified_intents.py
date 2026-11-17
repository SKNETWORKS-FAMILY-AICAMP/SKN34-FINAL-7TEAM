import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("unified", Path(__file__).with_name("prepare_unified_intents.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def example(split="train", text="차가운 커피 한 잔", group="group"):
    return {
        "id": "single:example", "dataset": "single", "split": split,
        "group_id": group, "text": text,
    }


class UnifiedPreprocessingTests(unittest.TestCase):
    def test_unifies_intent_and_preserves_original_without_inventing_action(self):
        item = module.convert({
            "id": "123", "split": "train", "group_id": "g",
            "text_raw": "우유가 있나요?", "text": "우유가 있나요?",
            "intent": "메뉴_문의", "source": "합성",
        }, "single", "train")
        self.assertEqual(item["intents"], ["메뉴_정보"])
        self.assertEqual(item["original_intents"], ["메뉴_문의"])
        self.assertEqual(item["expected_actions"], [])
        self.assertEqual(item["review_key"], "단일 의도:123")
        self.assertEqual(item["split"], "train")

    def test_multiple_intents_and_context_are_preserved(self):
        row = module.convert({
            "scenario_id": "456", "split": "validation", "group_id": "g",
            "utterance_raw": "이거랑 화장실", "text": "이거랑 화장실",
            "intents": ["메뉴_정보", "매장_안내"], "source": "합성",
            "expected_actions": ["lookup_store_info"], "expected_slots": {"menu_ref": "라떼"},
            "conversation_history": [{"role": "user", "text": "라떼"}],
            "current_state": {"cart": []},
            "note": "지역 발화를 대표하지 않는 예시",
        }, "multi", "validation")
        self.assertEqual(row["intents"], ["메뉴_정보", "매장_안내"])
        self.assertEqual(row["expected_slots"], {"menu_ref": "라떼"})
        self.assertEqual(row["review_key"], "문맥 시나리오:456")
        self.assertEqual(row["note"], "지역 발화를 대표하지 않는 예시")

    def test_cross_split_group_and_exact_text_rejected(self):
        for rows in (
            [example(), {**example("test", "다른 문장"), "id": "single:two"}],
            [example(), {**example("test", group="different"), "id": "single:two"}],
        ):
            with self.assertRaises(ValueError):
                module.validate(rows)

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileExistsError):
                module.write_new_output(Path(temp), [], {})

    def test_unknown_labels_are_not_silently_coerced(self):
        raw = {"id": "1", "split": "train", "group_id": "g", "text_raw": "x",
               "text": "x", "intent": "새_의도"}
        with self.assertRaises(ValueError):
            module.convert(raw, "single", "train")


if __name__ == "__main__":
    unittest.main()

