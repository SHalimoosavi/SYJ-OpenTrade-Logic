import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.import_hts_data import build_tree  # noqa: E402
from core.gri_engine import GRIEngine  # noqa: E402


class TestImporterAndTerseHeadingMatching(unittest.TestCase):
    """
    Regression test for a real bug found while building v0.3.0: real USITC
    heading text is terse legal language that often doesn't contain the
    everyday product words a user types. Product-identifying words usually
    live at the subheading level. The GRI engine must still find the right
    heading in that case, not just when hand-curated sample keywords happen
    to include the search terms.
    """

    def setUp(self):
        fixture = [
            {"htsno": "84", "description": "Nuclear reactors, boilers, machinery and mechanical appliances",
             "indent": "0", "general": "", "units": []},
            {"htsno": "8471", "description": "Automatic data processing machines and units thereof",
             "indent": "1", "general": "", "units": []},
            {"htsno": "8471.30.00", "description": "Portable ADP machines, weighing not more than 10 kg laptop notebook",
             "indent": "2", "general": "Free", "units": ["No."]},
            {"htsno": "8471.41.00", "description": "Other ADP machines comprising a CPU and I/O unit desktop workstation",
             "indent": "2", "general": "Free", "units": ["No."]},
        ]
        self.tree = build_tree(fixture)
        fd, self.data_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(self.data_path, "w") as f:
            json.dump(self.tree, f)
        self.engine = GRIEngine(self.data_path)

    def tearDown(self):
        os.remove(self.data_path)

    def test_importer_builds_correct_chapter_heading_subheading_shape(self):
        self.assertEqual(len(self.tree["chapters"]), 1)
        chapter = self.tree["chapters"][0]
        self.assertEqual(chapter["code"], "84")
        self.assertEqual(len(chapter["children"]), 1)
        heading = chapter["children"][0]
        self.assertEqual(heading["code"], "8471")
        self.assertEqual(len(heading["children"]), 2)

    def test_classification_finds_subheading_even_when_heading_text_has_no_overlap(self):
        result = self.engine.classify("portable laptop notebook computer")
        self.assertTrue(result.is_classified)
        self.assertEqual(result.final_code, "8471.30.00")

    def test_classification_distinguishes_between_sibling_subheadings(self):
        result = self.engine.classify("desktop workstation computer")
        self.assertTrue(result.is_classified)
        self.assertEqual(result.final_code, "8471.41.00")


class TestMultiChapterDetection(unittest.TestCase):
    """
    Regression test for a real bug found running import_hts_data.py against
    the LIVE USITC feed on 2026-07-21: the real data emits very few bare
    2-digit chapter rows (sometimes only one across 35,000+ records), so
    chapter boundaries must be derived from each heading's own code prefix,
    not from waiting for a dedicated chapter row.
    """

    def test_new_chapter_detected_even_without_a_bare_2digit_row(self):
        fixture = [
            {"htsno": "01", "description": "LIVE ANIMALS", "indent": "0", "general": "", "units": []},
            {"htsno": "0101", "description": "Live horses, asses, mules", "indent": "1", "general": "", "units": []},
            {"htsno": "0101.30.00", "description": "Asses", "indent": "2", "general": "6.8%", "units": ["No."]},
            # No bare "84" chapter row at all -- this is the gap that broke it live
            {"htsno": "8471", "description": "Automatic data processing machines", "indent": "1", "general": "", "units": []},
            {"htsno": "8471.30.00", "description": "Portable ADP machines", "indent": "2", "general": "Free", "units": ["No."]},
        ]
        tree = build_tree(fixture)
        codes = [c["code"] for c in tree["chapters"]]
        self.assertEqual(codes, ["01", "84"])
        self.assertEqual(tree["chapters"][1]["children"][0]["code"], "8471")


class TestChapter99DoesNotOutrankRealHeadings(unittest.TestCase):
    """
    Regression test for a real bug found spot-checking v0.3.0 against the
    LIVE USITC feed: "cordless electric drill" classified to a Chapter 99
    special tariff provision (9902.15.81) instead of the correct heading
    8467.21.00, purely because the Ch.99 entry's very long technical
    description happened to contain more literal overlapping words
    ("drill-bits" -> tokens "drill"+"bits") than the real heading's own
    plural phrasing ("Drills of all kinds" -> "drills" != "drill" without
    stemming). Fixed via _stem() normalization in core/gri_engine.py and a
    scoring penalty for synthesized/structurally-incomplete headings.
    """

    def test_real_heading_wins_over_verbose_chapter99_entry(self):
        fixture = [
            {"htsno": "84", "description": "Nuclear reactors, boilers, machinery and mechanical appliances",
             "indent": "0", "general": "", "units": []},
            {"htsno": "8467", "description": "Tools for working in the hand, pneumatic, hydraulic or with self-contained motor",
             "indent": "1", "general": "", "units": []},
            {"htsno": "8467.21.00", "description": "Drills of all kinds, hand-held, electric motor",
             "indent": "2", "general": "1.7%", "units": ["No."]},
            {"htsno": "99", "description": "TEMPORARY MODIFICATIONS", "indent": "0", "general": "", "units": []},
            {"htsno": "9902.15.81",
             "description": ("Rotary drill, hammer and chiseling tools with self-contained electric motor "
                              "(provided for in 8467.21.00), each with pneumatic hammering mechanism that "
                              "engages with slotted drive drill-bits and an electromechanical mechanism"),
             "indent": "1", "general": "Free", "units": ["No."]},
        ]
        tree = build_tree(fixture)
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w") as f:
            json.dump(tree, f)
        try:
            result = GRIEngine(path).classify("cordless electric drill")
            self.assertEqual(result.final_code, "8467.21.00")
        finally:
            os.remove(path)


class TestIndentNestingDoesNotLeakAcrossBranches(unittest.TestCase):
    """
    Regression test for a real bug found spot-checking v0.3.0 against the
    LIVE USITC feed: "cotton t-shirt" classified to heading 6211
    (track suits/swimwear/other garments) instead of the correct heading
    6109 (T-shirts, singlets). Cause: nested grouping rows ("Other
    garments:" -> "Women's or girls':" -> "Of cotton:") were being folded
    flatly onto the whole heading instead of scoped to their actual branch
    via the `indent` field. Fixed with an indent-keyed context stack in
    scripts/import_hts_data.py.
    """

    def test_cotton_context_does_not_leak_from_one_heading_to_a_sibling_heading(self):
        fixture = [
            {"htsno": "61", "description": "Articles of apparel, knitted or crocheted",
             "indent": "0", "general": "", "units": []},
            {"htsno": "6109", "description": "T-shirts, singlets and other vests, knitted or crocheted",
             "indent": "1", "general": "", "units": []},
            {"htsno": "6109.10.00", "description": "Of cotton", "indent": "2", "general": "16.5%", "units": ["doz."]},
            {"htsno": "6211", "description": "Track suits, ski-suits and swimwear; other garments",
             "indent": "1", "general": "", "units": []},
            {"htsno": "", "description": "Other garments, women's or girls':", "indent": "2", "general": "", "units": []},
            {"htsno": "", "description": "Of cotton:", "indent": "3", "general": "", "units": []},
            {"htsno": "6211.42.00", "description": "Track suits", "indent": "4", "general": "8.1%", "units": ["No."]},
        ]
        tree = build_tree(fixture)
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w") as f:
            json.dump(tree, f)
        try:
            result = GRIEngine(path).classify("cotton t-shirt")
            self.assertEqual(result.final_code, "6109.10.00")
        finally:
            os.remove(path)


class TestStemmerHandlesSilentEPlurals(unittest.TestCase):
    """
    Regression test for a real bug found spot-checking v0.4.0 against the
    LIVE USITC feed: "android smartphone" classified to a Chapter 99
    special provision for phone CASES instead of the real heading 8517's
    "Smartphones" subheading. Root cause: _stem() stripped "es" from
    "smartphones", giving "smartphon" (missing the final e) which never
    matched the query token "smartphone". Fixed by only stripping a
    single trailing "s" for this domain's vocabulary (phone, case, code,
    machine, etc. all end in a silent e before the plural s).
    """

    def test_smartphones_heading_beats_chapter99_case_provision(self):
        fixture = [
            {"htsno": "85", "description": "Electrical machinery and equipment",
             "indent": "0", "general": "", "units": []},
            {"htsno": "8517",
             "description": ("Telephone sets, including smartphones and other telephones for cellular "
                              "networks or for other wireless networks; other apparatus for the transmission"),
             "indent": "1", "general": "", "units": []},
            {"htsno": "8517.13.00.00", "description": "Smartphones", "indent": "2", "general": "Free", "units": ["No."]},
            {"htsno": "99", "description": "TEMPORARY MODIFICATIONS", "indent": "0", "general": "", "units": []},
            {"htsno": "9902.12.09",
             "description": ("Back-shell style smartphone cases of hard plastics, each incorporating "
                              "flexible rubber over command buttons and specially fitted rigid plastic "
                              "clip with adjustable neoprene fabric armband (provided for in subheading 3926.90.99)."),
             "indent": "1", "general": "Free", "units": ["No."]},
        ]
        tree = build_tree(fixture)
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w") as f:
            json.dump(tree, f)
        try:
            result = GRIEngine(path).classify("android smartphone")
            self.assertEqual(result.final_code, "8517.13.00.00")
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
