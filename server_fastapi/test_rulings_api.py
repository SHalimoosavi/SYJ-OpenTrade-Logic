"""
SYJ OpenTrade Logic - Rulings search API integration tests
=============================================================
Run on your machine (needs the full FastAPI stack installed):
    python3 -m unittest server_fastapi.test_rulings_api -v
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRulingsAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        local_tmp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".test_tmp")
        os.makedirs(local_tmp_dir, exist_ok=True)
        cls.tmp_db_fd, cls.tmp_db_path = tempfile.mkstemp(suffix=".db", dir=local_tmp_dir)
        os.close(cls.tmp_db_fd)
        os.remove(cls.tmp_db_path)
        os.environ["SYJ_DATABASE_URL"] = f"sqlite:///{cls.tmp_db_path}"

        # Deterministic against the small sample HTS dataset, same reasoning
        # as test_main.py -- this file tests API mechanics, not live-data
        # classification accuracy.
        sample_data_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "hts_sample.json"
        )
        os.environ["SYJ_HTS_DATA_PATH"] = sample_data_path

        from fastapi.testclient import TestClient
        from server_fastapi.database import init_db
        from server_fastapi.main import app

        init_db()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.tmp_db_path):
            os.remove(cls.tmp_db_path)

    def test_rulings_search_returns_relevant_results(self):
        resp = self.client.get("/rulings/search", params={"q": "cordless drill classification"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertGreater(body["count"], 0)
        self.assertEqual(body["results"][0]["id"], "NY J80129")

    def test_rulings_search_respects_limit(self):
        resp = self.client.get("/rulings/search", params={"q": "classification", "limit": 2})
        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(len(resp.json()["results"]), 2)

    def test_rulings_search_requires_query_param(self):
        resp = self.client.get("/rulings/search")
        self.assertEqual(resp.status_code, 422)  # FastAPI validation error, q is required

    def test_classify_includes_related_rulings(self):
        resp = self.client.post("/classify", json={"description": "cordless electric drill"})
        self.assertEqual(resp.status_code, 201, resp.text)
        body = resp.json()
        self.assertIn("related_rulings", body)
        self.assertGreater(len(body["related_rulings"]), 0)
        ruling_ids = {r["id"] for r in body["related_rulings"]}
        self.assertIn("NY J80129", ruling_ids)

    def test_classify_related_rulings_persist_and_are_retrievable(self):
        created = self.client.post("/classify", json={"description": "cotton knitted t-shirt"}).json()
        fetched = self.client.get(f"/classifications/{created['id']}").json()
        self.assertIn("related_rulings", fetched)
        self.assertEqual(fetched["related_rulings"], created["related_rulings"])

    def test_classify_with_unresolvable_description_has_empty_related_rulings_or_text_matches_only(self):
        # A nonsense description won't classify, so there's no final_code to
        # match rulings by HTS prefix -- but lexical text matches can still
        # surface if any (there shouldn't be any for pure nonsense).
        resp = self.client.post("/classify", json={"description": "xyzzy quantum flux capacitor"})
        body = resp.json()
        self.assertFalse(body["is_classified"])
        # Should not error out even with no final_code to look up
        self.assertIn("related_rulings", body)


if __name__ == "__main__":
    unittest.main()
