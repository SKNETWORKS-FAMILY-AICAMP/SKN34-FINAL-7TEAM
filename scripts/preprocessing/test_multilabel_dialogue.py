import unittest
import prepare_multilabel_dialogue as ds

class MultilabelTests(unittest.TestCase):
    def test_groups_and_text_are_disjoint_between_splits(self):
        rows = ds.build()
        groups = {s:{r["group_id"] for r in rows if r["split"] == s} for s in ("train","validation","test")}
        texts = {s:{r["utterance"] for r in rows if r["split"] == s} for s in groups}
        for a, b in (("train","validation"),("train","test"),("validation","test")):
            self.assertFalse(groups[a] & groups[b])
            self.assertFalse(texts[a] & texts[b])
    def test_multi_intent_retains_both_requests(self):
        examples = [r for r in ds.build() if r["category"] == "복합요청"]
        self.assertTrue(examples)
        for row in examples:
            self.assertIn("매장_안내", row["intents"])
            self.assertTrue("메뉴_정보" in row["intents"] or "주문_추가" in row["intents"])
    def test_each_label_is_represented_in_each_split(self):
        rows=ds.build()
        labels={s:{label for r in rows if r["split"] == s for label in r["intents"]} for s in ("train","validation","test")}
        self.assertEqual(labels["train"],labels["validation"])
        self.assertEqual(labels["train"],labels["test"])
    def test_ambiguous_and_dialect_labels_are_not_coerced(self):
        rows=ds.build()
        self.assertTrue(all(r["intents"] == ["주문_삭제"] for r in rows if r["group_id"]=="ambiguous_holdout"))
        self.assertTrue(all(r["intents"] == ["매장_안내"] for r in rows if r["group_id"]=="dialect_holdout"))
    def test_train_context_is_preserved(self):
        row=next(r for r in ds.build() if r["group_id"]=="train_context")
        self.assertTrue(row["conversation_history"])
        self.assertTrue(row["current_state"]["cart"])

if __name__=="__main__":
    unittest.main()