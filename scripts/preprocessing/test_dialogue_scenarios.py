import copy
import unittest
import prepare_dialogue_scenarios as ds

class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.rows = ds.build_scenarios()

    def test_groups_and_text_are_disjoint_between_splits(self):
        ds.validate(self.rows)
        dev = [r for r in self.rows if r["split"] == "development"]
        holdout = [r for r in self.rows if r["split"] == "holdout"]
        self.assertFalse({r["group_id"] for r in dev} & {r["group_id"] for r in holdout})
        self.assertFalse({r["utterance"] for r in dev} & {r["utterance"] for r in holdout})

    def test_multi_request_contains_multiple_expected_actions(self):
        examples = [r for r in self.rows if r["category"] == "복합요청"]
        self.assertTrue(examples)
        self.assertTrue(all("lookup_store_info" in r["expected_actions"] for r in examples))
        self.assertTrue(all(("lookup_menu_attribute" in r["expected_actions"] or "add_if_complete" in r["expected_actions"]) for r in examples))

    def test_ambiguous_target_never_changes_cart_first(self):
        for row in self.rows:
            if row["category"] == "정보누락":
                self.assertIn("ask_clarification", row["expected_actions"])
                self.assertIn("do_not_change_cart_before_clarification", row["expected_actions"])

    def test_water_and_allergy_have_safe_expected_behavior(self):
        for row in self.rows:
            if row["category"] == "따뜻한물":
                self.assertIn("guide_customer_to_staff", row["expected_actions"])
                self.assertIn("do_not_claim_staff_called", row["expected_actions"])
            if row["category"] == "알레르기":
                self.assertIn("do_not_infer_safety", row["expected_actions"])

    def test_duplicate_utterances_fail_validation(self):
        rows = copy.deepcopy(self.rows)
        rows.append(copy.deepcopy(rows[0]))
        with self.assertRaises(ValueError):
            ds.validate(rows)

if __name__ == "__main__":
    unittest.main()