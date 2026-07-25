import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server_fastapi.catalog_import import (  # noqa: E402
    parse_csv_bytes,
    parse_excel_bytes,
    parse_upload,
    ImportParseError,
)


class TestCSVImport(unittest.TestCase):
    def test_valid_rows_parse_correctly(self):
        content = (
            "SKU,Name,Description,HTS_Code,Duty_Rate\n"
            "DRILL-001,Cordless Electric Drill,18V battery powered drill,8467.21.00.10,Free\n"
            "TSHIRT-100,Cotton T-Shirt White,100% cotton crew neck,6109.10.00.04,16.5%\n"
        )
        results = parse_csv_bytes(content.encode("utf-8"))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["product"]["sku"], "DRILL-001")
        self.assertEqual(results[0]["product"]["hts_code"], "8467.21.00.10")
        self.assertIsNone(results[0]["error"])

    def test_missing_name_produces_row_level_error_not_a_crash(self):
        content = "sku,name\nBAD-ROW,\n"
        results = parse_csv_bytes(content.encode("utf-8"))
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0]["product"])
        self.assertIn("name", results[0]["error"])

    def test_missing_sku_produces_row_level_error(self):
        content = "sku,name\n,Widget\n"
        results = parse_csv_bytes(content.encode("utf-8"))
        self.assertIsNone(results[0]["product"])
        self.assertIn("sku", results[0]["error"])

    def test_blank_rows_are_skipped(self):
        content = "sku,name\nA-1,Widget\n,,\nB-2,Gadget\n"
        results = parse_csv_bytes(content.encode("utf-8"))
        self.assertEqual(len(results), 2)

    def test_missing_required_column_raises_parse_error(self):
        with self.assertRaises(ImportParseError):
            parse_csv_bytes(b"Name,Description\nWidget,A thing\n")

    def test_empty_file_raises_parse_error(self):
        with self.assertRaises(ImportParseError):
            parse_csv_bytes(b"")

    def test_utf8_bom_is_handled(self):
        content = "\ufeffsku,name\nX-1,Widget\n".encode("utf-8")
        results = parse_csv_bytes(content)
        self.assertEqual(results[0]["product"]["sku"], "X-1")

    def test_column_order_does_not_matter(self):
        content = "name,hts_code,sku\nWidget,1234.56,X-1\n"
        results = parse_csv_bytes(content.encode("utf-8"))
        self.assertEqual(results[0]["product"]["sku"], "X-1")
        self.assertEqual(results[0]["product"]["hts_code"], "1234.56")


class TestExcelImport(unittest.TestCase):
    def _make_xlsx(self, rows):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        for row in rows:
            ws.append(row)
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def test_valid_rows_parse_correctly(self):
        xlsx = self._make_xlsx([
            ["sku", "name", "description", "hts_code", "duty_rate"],
            ["DRILL-001", "Cordless Electric Drill", "18V battery powered", "8467.21.00.10", "Free"],
        ])
        results = parse_excel_bytes(xlsx)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["product"]["sku"], "DRILL-001")

    def test_blank_rows_are_skipped(self):
        xlsx = self._make_xlsx([
            ["sku", "name"],
            ["A-1", "Widget"],
            [None, None],
            ["B-2", "Gadget"],
        ])
        results = parse_excel_bytes(xlsx)
        self.assertEqual(len(results), 2)

    def test_error_rows_are_collected_not_raised(self):
        xlsx = self._make_xlsx([
            ["sku", "name"],
            ["BAD-SKU", None],
        ])
        results = parse_excel_bytes(xlsx)
        self.assertIsNotNone(results[0]["error"])


class TestUploadDispatch(unittest.TestCase):
    def test_dispatches_csv_by_extension(self):
        results = parse_upload("products.csv", b"sku,name\nA-1,Widget\n")
        self.assertEqual(results[0]["product"]["sku"], "A-1")

    def test_dispatches_csv_case_insensitively(self):
        results = parse_upload("products.CSV", b"sku,name\nA-1,Widget\n")
        self.assertEqual(results[0]["product"]["sku"], "A-1")

    def test_rejects_unsupported_extension(self):
        with self.assertRaises(ImportParseError):
            parse_upload("products.txt", b"whatever")


if __name__ == "__main__":
    unittest.main()
