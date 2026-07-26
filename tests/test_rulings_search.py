import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rulings_search import RulingsSearchIndex, _tokenize  # noqa: E402

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cross_rulings_sample.json")


class TestRulingsSearchIndex(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = RulingsSearchIndex(DATA_PATH)

    def test_index_loads_all_rulings(self):
        self.assertEqual(len(self.index.rulings), 6)

    def test_drill_query_ranks_drill_ruling_first(self):
        results = self.index.search("cordless drill classification", top_k=3)
        self.assertTrue(results)
        self.assertEqual(results[0].ruling.id, "NY J80129")

    def test_apple_watch_query_ranks_watch_ruling_first(self):
        results = self.index.search("apple watch essential character", top_k=3)
        self.assertTrue(results)
        self.assertEqual(results[0].ruling.id, "HQ H270725")

    def test_tshirt_query_ranks_tshirt_ruling_first(self):
        results = self.index.search("cotton t-shirt knit classification", top_k=3)
        self.assertTrue(results)
        self.assertEqual(results[0].ruling.id, "NY N219388")

    def test_bluetooth_query_ranks_bluetooth_ruling_first(self):
        results = self.index.search("bluetooth earphones bundled with phone", top_k=3)
        self.assertTrue(results)
        self.assertEqual(results[0].ruling.id, "HQ H245902")

    def test_multifunction_tool_query_ranks_big_scrub_first(self):
        results = self.index.search("multi-function tool set principal function", top_k=3)
        self.assertTrue(results)
        self.assertEqual(results[0].ruling.id, "M80652")

    def test_empty_query_returns_no_results(self):
        self.assertEqual(self.index.search(""), [])

    def test_nonsense_query_returns_no_or_low_results(self):
        results = self.index.search("xyzzy quantum flux capacitor unrelated nonsense")
        # Either no results, or nothing above a meaningful score
        for r in results:
            self.assertLess(r.score, 1.0)

    def test_results_are_sorted_descending_by_score(self):
        results = self.index.search("classification tariff")
        scores = [r.score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_top_k_is_respected(self):
        results = self.index.search("classification", top_k=2)
        self.assertLessEqual(len(results), 2)

    def test_to_dict_is_json_serializable(self):
        import json
        results = self.index.search("cordless drill")
        for r in results:
            json.dumps(r.to_dict())  # raises if not serializable

    def test_search_by_hts_prefix_finds_related_rulings(self):
        # 8467.21.00.10 -> prefix 8467 -> should match drill rulings
        matches = self.index.search_by_hts_prefix("8467.21.00.10")
        matched_ids = {m.id for m in matches}
        self.assertIn("NY J80129", matched_ids)

    def test_search_by_hts_prefix_with_no_code_returns_empty(self):
        self.assertEqual(self.index.search_by_hts_prefix(None), [])

    def test_search_by_hts_prefix_with_unknown_code_returns_empty(self):
        self.assertEqual(self.index.search_by_hts_prefix("9999.99.99"), [])

    def test_matched_terms_are_actually_in_the_query(self):
        results = self.index.search("cordless drill classification")
        query_tokens = set(_tokenize("cordless drill classification"))
        for r in results:
            for term in r.matched_terms:
                self.assertIn(term, query_tokens)


if __name__ == "__main__":
    unittest.main()
