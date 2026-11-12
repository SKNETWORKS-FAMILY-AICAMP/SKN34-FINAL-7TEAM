import unittest

from prepare_store import build_facts


class StoreDataTests(unittest.TestCase):
    def setUp(self):
        self.sample = {"store_id": "demo", "restroom_location": "입구 근처", "restroom_passcode": "demo-code",
                       "warm_water_guidance": "직원에게 문의", "opens_at": "09:00", "closes_at": "21:00"}

    def test_restroom_location_and_code_apply_to_both(self):
        facts = {f["id"]: f for f in build_facts(self.sample)["facts"]}
        self.assertEqual(facts["restroom.location"]["applies_to"], ["남성", "여성"])
        self.assertEqual(facts["restroom.passcode"]["applies_to"], ["남성", "여성"])

    def test_opening_days_remain_unknown(self):
        facts = {f["id"]: f for f in build_facts(self.sample)["facts"]}
        self.assertIsNone(facts["hours.open"]["days"])
        self.assertIsNone(facts["hours.close"]["days"])

    def test_missing_code_is_error(self):
        self.sample["restroom_passcode"] = ""
        with self.assertRaises(ValueError):
            build_facts(self.sample)

    def test_invalid_hour_is_error(self):
        self.sample["opens_at"] = "25:00"
        with self.assertRaises(ValueError):
            build_facts(self.sample)


if __name__ == "__main__":
    unittest.main()
