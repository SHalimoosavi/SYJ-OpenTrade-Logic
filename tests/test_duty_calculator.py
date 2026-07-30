import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.duty_calculator import DutyCalculator, parse_ad_valorem_rate  # noqa: E402

TRADE_PROGRAMS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "trade_programs_sample.json"
)
ADCVD_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "adcvd_sample.json")


class TestRateParsing(unittest.TestCase):
    def test_free_parses_to_zero(self):
        self.assertEqual(parse_ad_valorem_rate("Free"), 0.0)

    def test_percentage_parses_correctly(self):
        self.assertEqual(parse_ad_valorem_rate("16.5%"), 0.165)
        self.assertEqual(parse_ad_valorem_rate("1.7%"), 0.017)

    def test_specific_rate_returns_none(self):
        self.assertIsNone(parse_ad_valorem_rate("$0.28/kg"))

    def test_compound_rate_returns_none(self):
        self.assertIsNone(parse_ad_valorem_rate("5.3 cents/kg + 5%"))

    def test_none_input_returns_none(self):
        self.assertIsNone(parse_ad_valorem_rate(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(parse_ad_valorem_rate(""))


class TestDutyCalculator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calc = DutyCalculator(TRADE_PROGRAMS_PATH, ADCVD_PATH)

    def test_data_files_have_required_disclaimer_fields(self):
        with open(TRADE_PROGRAMS_PATH) as f:
            data = json.load(f)
        self.assertIn("as_of_date", data)
        self.assertIn("disclaimer", data)
        self.assertIn("official_sources", data)

    def test_section301_applies_to_china_only(self):
        r_china = self.calc.calculate("8467.21.00.10", "CN", 10000.0, "1.7%")
        r_vietnam = self.calc.calculate("8467.21.00.10", "VN", 10000.0, "1.7%")
        self.assertEqual(len(r_china.program_duties), 1)
        self.assertEqual(len(r_vietnam.program_duties), 0)

    def test_section301_amount_is_correct(self):
        r = self.calc.calculate("8467.21.00.10", "CN", 10000.0, "1.7%")
        self.assertAlmostEqual(r.total_duty_rate, 0.092, places=4)
        self.assertAlmostEqual(r.total_duty_amount, 920.0, places=2)

    def test_section232_applies_regardless_of_country(self):
        r_brazil = self.calc.calculate("7208.10.00", "BR", 50000.0, "Free")
        r_japan = self.calc.calculate("7208.10.00", "JP", 50000.0, "Free")
        self.assertEqual(len(r_brazil.program_duties), 1)
        self.assertEqual(len(r_japan.program_duties), 1)
        self.assertEqual(r_brazil.program_duties[0].program, "Section 232 - Steel")

    def test_no_applicable_programs_for_unrelated_product(self):
        r = self.calc.calculate("6109.10.00", "DE", 5000.0, "16.5%")
        self.assertEqual(len(r.program_duties), 0)
        self.assertEqual(r.total_duty_rate, 0.165)

    def test_adcvd_flag_for_known_scope(self):
        r = self.calc.calculate("7604.29.00", "CN", 20000.0, "Free")
        self.assertEqual(len(r.adcvd_flags), 1)
        self.assertIn("Aluminum extrusions", r.adcvd_flags[0].product_scope)
        self.assertTrue(any("ADCVD" in w or "AD/CVD" in w for w in r.warnings))

    def test_no_adcvd_flag_for_unrelated_country(self):
        r = self.calc.calculate("7604.29.00", "CA", 20000.0, "Free")
        self.assertEqual(len(r.adcvd_flags), 0)

    def test_compound_rate_produces_warning_and_no_total(self):
        r = self.calc.calculate("0402.10.00", "NZ", 5000.0, "$1.111/kg")
        self.assertIsNone(r.base_duty_rate)
        self.assertIsNone(r.total_duty_rate)
        self.assertGreater(len(r.warnings), 0)

    def test_missing_rate_produces_warning(self):
        r = self.calc.calculate("8467.21.00.10", "CN", 10000.0, None)
        self.assertIsNone(r.base_duty_rate)
        self.assertGreater(len(r.warnings), 0)

    def test_to_dict_is_json_serializable(self):
        r = self.calc.calculate("8467.21.00.10", "CN", 10000.0, "1.7%")
        json.dumps(r.to_dict())  # raises if not serializable

    def test_result_includes_disclaimer_and_as_of_date(self):
        r = self.calc.calculate("8467.21.00.10", "CN", 10000.0, "1.7%")
        self.assertTrue(r.disclaimer)
        self.assertTrue(r.as_of_date)

    def test_country_matching_is_case_insensitive(self):
        r_lower = self.calc.calculate("8467.21.00.10", "cn", 10000.0, "1.7%")
        r_upper = self.calc.calculate("8467.21.00.10", "CN", 10000.0, "1.7%")
        self.assertEqual(len(r_lower.program_duties), len(r_upper.program_duties))
        self.assertEqual(r_lower.country_of_origin, "CN")

    def test_zero_declared_value_does_not_crash(self):
        r = self.calc.calculate("8467.21.00.10", "CN", 0.0, "1.7%")
        self.assertEqual(r.base_duty_amount, 0.0)


if __name__ == "__main__":
    unittest.main()
