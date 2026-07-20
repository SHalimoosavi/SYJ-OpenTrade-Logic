import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gri_engine import GRIEngine  # noqa: E402
from core.models import GRIRule  # noqa: E402

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "hts_sample.json")


class TestGRIEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GRIEngine(DATA_PATH)

    def test_laptop_classifies_to_8471_30(self):
        result = self.engine.classify("15 inch portable laptop notebook computer")
        self.assertTrue(result.is_classified)
        self.assertEqual(result.final_code, "8471.30")
        self.assertGreater(result.confidence, 0.0)
        self.assertEqual(result.duty_rate, "Free")

    def test_cotton_tshirt_classifies_to_6109_10(self):
        result = self.engine.classify("men's cotton t-shirt knitted")
        self.assertTrue(result.is_classified)
        self.assertEqual(result.final_code, "6109.10")

    def test_polyester_tshirt_classifies_to_6109_90(self):
        result = self.engine.classify("polyester blend synthetic tee shirt")
        self.assertTrue(result.is_classified)
        self.assertEqual(result.final_code, "6109.90")

    def test_cordless_drill_classifies_to_8467_21(self):
        result = self.engine.classify("cordless electric hand drill")
        self.assertTrue(result.is_classified)
        self.assertEqual(result.final_code, "8467.21")

    def test_smartphone_classifies_to_8517_13(self):
        result = self.engine.classify("android smartphone mobile phone")
        self.assertTrue(result.is_classified)
        self.assertEqual(result.final_code, "8517.13")

    def test_unmatched_product_is_unresolved_not_guessed(self):
        result = self.engine.classify("xyzzy quantum flux capacitor widget")
        self.assertFalse(result.is_classified)
        self.assertIsNone(result.final_code)
        self.assertIsNotNone(result.unresolved_reason)

    def test_empty_description_is_unresolved(self):
        result = self.engine.classify("")
        self.assertFalse(result.is_classified)

    def test_decision_path_is_never_empty_for_classified_result(self):
        result = self.engine.classify("cordless electric hand drill")
        self.assertGreater(len(result.decision_path), 0)
        first_step = result.decision_path[0]
        self.assertEqual(first_step.rule_applied, GRIRule.GRI_1)

    def test_decision_path_includes_gri6_when_subheading_resolved(self):
        result = self.engine.classify("men's cotton t-shirt knitted")
        rules_applied = [s.rule_applied for s in result.decision_path]
        self.assertIn(GRIRule.GRI_6, rules_applied)

    def test_to_dict_is_json_serializable(self):
        import json
        result = self.engine.classify("android smartphone")
        json.dumps(result.to_dict())  # raises if not serializable

    def test_alternatives_never_include_the_selected_code(self):
        result = self.engine.classify("men's cotton t-shirt knitted")
        alt_codes = [a.code for a in result.alternatives]
        self.assertNotIn(result.final_code, alt_codes)

    def test_router_classifies_under_correct_subheading(self):
        result = self.engine.classify("wifi router modem network device")
        self.assertTrue(result.is_classified)
        self.assertEqual(result.final_code, "8517.62")


if __name__ == "__main__":
    unittest.main()
