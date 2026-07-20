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


if __name__ == "__main__":
    unittest.main()
