import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from prepare_approved_training import build, write_new_output


def draft(key="train1", split="train", text="아메리카노 하나"):
    return {
        "id": "source:" + key, "review_key": key, "split": split,
        "group_id": "group-" + key, "text": text, "text_raw": text,
        "intents": ["주문_추가"], "original_intents": ["주문_추가"],
        "source": "합성", "conversation_history": [], "current_state": {},
    }


def review(row):
    return {
        "question_id": row["review_key"], "question_original": row["text"],
        "question_approved": row["text"], "expected_action": "메뉴를 찾아요",
        "expected_answer": "메뉴를 찾았어요", "review_comment": "",
        "review_status": "승인", "reviewed_at_utc": "2026-11-17T00:00:00",
        "original_split": row["split"], "group_id": row["group_id"],
    }


class ApprovedPreparationTest(unittest.TestCase):
    def setUp(self):
        self.train = draft()
        self.val = draft("val", "validation", "검증 문장")
        self.test = draft("test", "test", "시험 문장")
        self.sets = {"train": [self.train], "validation": [self.val], "test": [self.test]}
        self.review = review(self.train)

    def test_approved_unchanged_includes_only_human_reviewed(self):
        self.sets["train"].append(draft("not_reviewed"))
        records, manifest = build(self.sets, [self.review])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["question_approved"], self.train["text"])
        self.assertEqual(records[0]["intents"], ["주문_추가"])
        self.assertEqual(records[0]["expected_action_approved"], "메뉴를 찾아요")
        self.assertFalse(records[0]["label_review_required"])
        self.assertEqual(manifest["ready_count"], 1)

    def test_changed_question_is_quarantined_and_original_preserved(self):
        self.review["question_approved"] = "카페라떼 하나로 바꿔줘"
        records, manifest = build(self.sets, [self.review])
        self.assertTrue(records[0]["label_review_required"])
        self.assertEqual(records[0]["text_raw"], "아메리카노 하나")
        self.assertEqual(manifest["ready_count"], 0)
        with tempfile.TemporaryDirectory() as parent:
            out = Path(parent) / "new"
            write_new_output(out, records, manifest)
            self.assertEqual((out / "training_ready.jsonl").read_text(encoding="utf-8"), "")
            self.assertEqual(len((out / "needs_label_review.jsonl").read_text(encoding="utf-8").splitlines()), 1)
            with self.assertRaises(FileExistsError):
                write_new_output(out, records, manifest)

    def test_reject_missing_or_nonapproved_status(self):
        for status in (None, "반려", "수정 필요"):
            r = deepcopy(self.review)
            r["review_status"] = status
            with self.subTest(status=status), self.assertRaises(ValueError):
                build(self.sets, [r])

    def test_reject_duplicate_unknown_wrong_group_wrong_original(self):
        with self.assertRaises(ValueError):
            build(self.sets, [self.review, self.review])
        for field, value in (("question_id", "unknown"), ("group_id", "wrong"), ("question_original", "다른 원문")):
            r = deepcopy(self.review)
            r[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                build(self.sets, [r])

    def test_reject_empty_and_duplicate_approved_text(self):
        with self.assertRaises(ValueError):
            build(self.sets, [])
        another = draft("another", text=self.train["text"])
        self.sets["train"].append(another)
        with self.assertRaises(ValueError):
            build(self.sets, [self.review, review(another)])

    def test_reject_review_of_validation_or_test(self):
        for source in (self.val, self.test):
            with self.subTest(split=source["split"]), self.assertRaises(ValueError):
                build(self.sets, [review(source)])

    def test_reject_train_edit_to_test_text(self):
        self.review["question_approved"] = self.test["text"]
        with self.assertRaises(ValueError):
            build(self.sets, [self.review])

    def test_reject_missing_action(self):
        self.review["expected_action"] = "  "
        with self.assertRaises(ValueError):
            build(self.sets, [self.review])


if __name__ == "__main__":
    unittest.main()

