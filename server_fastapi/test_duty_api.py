"""
SYJ OpenTrade Logic - Duty calculator API integration tests
==============================================================
Run on your machine:
    python3 -m unittest server_fastapi.test_duty_api -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDutyAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from server_fastapi.main import app

        cls.client = TestClient(app)

    def test_calculate_duty_with_section301_applicable(self):
        resp = self.client.post("/duty/calculate", json={
            "hts_code": "8467.21.00.10",
            "country_of_origin": "CN",
            "declared_value": 10000.0,
            "general_duty_rate": "1.7%",
        })
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(len(body["program_duties"]), 1)
        self.assertAlmostEqual(body["total_duty_rate"], 0.092, places=4)
        self.assertAlmostEqual(body["total_duty_amount"], 920.0, places=2)
        self.assertTrue(body["disclaimer"])

    def test_calculate_duty_no_section301_for_other_country(self):
        resp = self.client.post("/duty/calculate", json={
            "hts_code": "8467.21.00.10",
            "country_of_origin": "VN",
            "declared_value": 10000.0,
            "general_duty_rate": "1.7%",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["program_duties"]), 0)

    def test_calculate_duty_flags_adcvd(self):
        resp = self.client.post("/duty/calculate", json={
            "hts_code": "7604.29.00",
            "country_of_origin": "CN",
            "declared_value": 20000.0,
            "general_duty_rate": "Free",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["adcvd_flags"]), 1)

    def test_calculate_duty_rejects_invalid_country_code_length(self):
        resp = self.client.post("/duty/calculate", json={
            "hts_code": "8467.21.00.10",
            "country_of_origin": "China",  # not a 2-letter code
            "declared_value": 10000.0,
        })
        self.assertEqual(resp.status_code, 422)

    def test_calculate_duty_rejects_negative_or_zero_value(self):
        resp = self.client.post("/duty/calculate", json={
            "hts_code": "8467.21.00.10",
            "country_of_origin": "CN",
            "declared_value": 0,
        })
        self.assertEqual(resp.status_code, 422)

    def test_calculate_duty_with_compound_rate_returns_warning_not_error(self):
        resp = self.client.post("/duty/calculate", json={
            "hts_code": "0402.10.00",
            "country_of_origin": "NZ",
            "declared_value": 5000.0,
            "general_duty_rate": "$1.111/kg",
        })
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIsNone(body["base_duty_rate"])
        self.assertGreater(len(body["warnings"]), 0)


if __name__ == "__main__":
    unittest.main()
