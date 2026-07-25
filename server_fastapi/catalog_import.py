"""
SYJ OpenTrade Logic - Product catalog CSV/Excel importer (v0.4.0)
====================================================================
Parses uploaded CSV or Excel files into a normalized list of product rows.
Deliberately separated from the FastAPI route and the database layer so
this parsing logic is fully unit-testable without needing FastAPI or
SQLAlchemy installed -- it only needs stdlib `csv` and `openpyxl`, both
available in this sandbox, so this file is tested for real, not just
described.

Expected columns (case-insensitive, order doesn't matter):
    sku*, name*, description, hts_code, duty_rate
    (* = required)

Design choice: this module never touches the database. It returns plain
dicts + per-row error strings; the FastAPI route layer decides what to do
with them (create/update Product rows). That keeps this importer testable
in total isolation.
"""

import csv
import io
from typing import List, Dict, Tuple, Optional

REQUIRED_COLUMNS = {"sku", "name"}
OPTIONAL_COLUMNS = {"description", "hts_code", "duty_rate"}
ALL_KNOWN_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS


class ImportParseError(Exception):
    """Raised for file-level problems (bad header, empty file, wrong format) --
    as opposed to row-level problems, which are collected and returned instead
    of raised, so one bad row doesn't abort an entire 500-row import."""
    pass


def _normalize_header(raw_header: List[str]) -> Dict[str, int]:
    """Map lowercased/stripped column name -> column index. Raises
    ImportParseError if a required column is missing."""
    normalized = {}
    for idx, col in enumerate(raw_header):
        key = (col or "").strip().lower()
        if key:
            normalized[key] = idx

    missing = REQUIRED_COLUMNS - normalized.keys()
    if missing:
        raise ImportParseError(
            f"Missing required column(s): {', '.join(sorted(missing))}. "
            f"Found columns: {', '.join(raw_header)}"
        )
    return normalized


def _row_to_product_dict(row: List[str], col_index: Dict[str, int], row_number: int) -> Tuple[Optional[dict], Optional[str]]:
    """Returns (product_dict, None) on success, or (None, error_message) on failure."""

    def get(col: str) -> Optional[str]:
        idx = col_index.get(col)
        if idx is None or idx >= len(row):
            return None
        val = row[idx]
        if val is None:
            return None
        val = str(val).strip()
        return val or None

    sku = get("sku")
    name = get("name")

    if not sku:
        return None, f"Row {row_number}: missing required 'sku'"
    if not name:
        return None, f"Row {row_number}: missing required 'name' for sku '{sku}'"

    return {
        "sku": sku,
        "name": name,
        "description": get("description"),
        "hts_code": get("hts_code"),
        "duty_rate": get("duty_rate"),
    }, None


def parse_csv_bytes(file_bytes: bytes) -> List[dict]:
    """
    Parses CSV file bytes into a list of dicts:
        {"row_number": int, "product": dict|None, "error": str|None}
    Raises ImportParseError if the file itself is unreadable or missing
    required columns -- individual bad rows are collected, not raised.
    """
    try:
        text = file_bytes.decode("utf-8-sig")  # handles BOM from Excel-exported CSVs
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise ImportParseError("CSV file is empty")

    col_index = _normalize_header(header)

    results = []
    for i, row in enumerate(reader, start=2):  # row 1 is the header
        if not any(cell.strip() for cell in row if cell):
            continue  # skip fully blank rows
        product, error = _row_to_product_dict(row, col_index, i)
        results.append({"row_number": i, "product": product, "error": error})

    if not results:
        raise ImportParseError("CSV file has a header but no data rows")

    return results


def parse_excel_bytes(file_bytes: bytes) -> List[dict]:
    """Same contract as parse_csv_bytes, for .xlsx files (via openpyxl)."""
    import openpyxl  # imported here so this module doesn't hard-fail to import if openpyxl is absent

    try:
        workbook = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as e:
        raise ImportParseError(f"Could not read Excel file: {e}")

    sheet = workbook.active
    rows_iter = sheet.iter_rows(values_only=True)

    try:
        header = list(next(rows_iter))
    except StopIteration:
        raise ImportParseError("Excel file is empty")

    header = [str(h) if h is not None else "" for h in header]
    col_index = _normalize_header(header)

    results = []
    for i, row in enumerate(rows_iter, start=2):
        row = list(row)
        if not any((cell is not None and str(cell).strip()) for cell in row):
            continue  # skip fully blank rows
        product, error = _row_to_product_dict(row, col_index, i)
        results.append({"row_number": i, "product": product, "error": error})

    if not results:
        raise ImportParseError("Excel file has a header but no data rows")

    return results


def parse_upload(filename: str, file_bytes: bytes) -> List[dict]:
    """Dispatches to the right parser based on file extension."""
    lower = filename.lower()
    if lower.endswith(".csv"):
        return parse_csv_bytes(file_bytes)
    elif lower.endswith(".xlsx") or lower.endswith(".xlsm"):
        return parse_excel_bytes(file_bytes)
    else:
        raise ImportParseError(f"Unsupported file type: {filename}. Use .csv or .xlsx")
