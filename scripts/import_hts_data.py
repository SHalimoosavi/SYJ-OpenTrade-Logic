#!/usr/bin/env python3
"""
SYJ OpenTrade Logic - Full HTS dataset importer
==================================================
Pulls the REAL, current, full Harmonized Tariff Schedule (chapters 01-99,
~17,000+ line items) from the official USITC REST API and converts it into
the nested chapter -> heading -> subheading JSON tree our GRIEngine expects
(same shape as data/hts_sample.json).

Official endpoint (confirmed from USITC's own "Harmonized Tariff Schedule
System User Guide", RESTful API section, base URL https://hts.usitc.gov/reststop):

    GET https://hts.usitc.gov/reststop/exportList
        ?from=0101&to=9999&format=JSON&styles=false

This MUST be run on a machine with real internet access -- it will not run
in a network-isolated sandbox. Run it on your Termux/dev machine:

    pip install requests --break-system-packages
    python3 scripts/import_hts_data.py

Output: data/hts_full.json

IMPORTANT -- run this with me watching the output the first time. The USITC
API's exact JSON field names have shifted between versions of their system
in the past (htsno/description/general/special/indent are the documented
fields as of the last time this was checked), so this script prints the raw
keys of the first record before doing anything else. If the printed keys
don't match FIELD NAMES below, stop and tell me what it printed so I can
adjust the parser with you rather than silently producing a broken dataset.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

EXPORT_URL = "https://hts.usitc.gov/reststop/exportList?from=0101&to=9999&format=JSON&styles=false"
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "hts_full.json")

# Documented field names per the USITC HTS user guide / observed API usage.
# If the printed sample record doesn't have these, the script will tell you
# and stop rather than guessing.
FIELD_HTSNO = "htsno"
FIELD_DESCRIPTION = "description"
FIELD_INDENT = "indent"
FIELD_GENERAL = "general"
FIELD_SPECIAL = "special"
FIELD_UNITS = "units"


def fetch_raw_hts() -> list:
    print(f"Fetching full HTS dataset from:\n  {EXPORT_URL}\n")
    print("This is ~17,000+ records; it may take 10-60 seconds depending on your connection.\n")
    req = urllib.request.Request(EXPORT_URL, headers={"User-Agent": "SYJ-OpenTrade-Logic/0.3.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw_bytes = resp.read()
    except urllib.error.URLError as e:
        print(f"ERROR: could not reach the USITC API: {e}")
        print("Check your internet connection. If this persists, the USITC endpoint")
        print("may be temporarily down (they do post maintenance windows) -- retry later.")
        sys.exit(1)

    data = json.loads(raw_bytes)
    if isinstance(data, dict) and "results" in data:
        data = data["results"]
    if not isinstance(data, list) or not data:
        print("ERROR: unexpected response shape from USITC API. Got:")
        print(json.dumps(data, indent=2)[:2000])
        sys.exit(1)

    print(f"Fetched {len(data)} raw records.\n")
    print("First record's keys (verify these match FIELD_* constants at the top of this script):")
    print(f"  {sorted(data[0].keys())}\n")
    return data


def to_int_indent(raw_indent) -> int:
    try:
        return int(raw_indent)
    except (TypeError, ValueError):
        return 0


def build_tree(raw_records: list) -> dict:
    """
    Convert the USITC flat, indent-based record list into our nested
    chapter -> heading -> subheading tree.

    Strategy:
      - A record is a CHAPTER root if its htsno is a bare 2-digit code (e.g. "84").
      - A record is a HEADING if its htsno is a 4-digit code with no dot (e.g. "8471"),
        or the first dotted segment when a 6/8/10-digit code appears without an
        explicit 4-digit heading row (some exports only emit dotted codes).
      - Everything else nests as a SUBHEADING under the most recently seen heading
        within the current chapter, using `indent` to track nesting depth for
        the un-numbered "descriptive" rows HTS uses (e.g. "Live animals:" with
        indented sub-rows below it that inherit the parent's classification code
        until a new htsno appears).
      - Rows with an empty description and empty htsno are separator rows and
        are skipped.
    """
    chapters_by_code = {}
    chapters_order = []
    current_chapter = None
    current_heading = None

    for rec in raw_records:
        htsno = (rec.get(FIELD_HTSNO) or "").strip()
        description = (rec.get(FIELD_DESCRIPTION) or "").strip()
        general = (rec.get(FIELD_GENERAL) or "").strip() or None
        units = rec.get(FIELD_UNITS) or []

        if not description:
            continue  # skip pure separator/blank rows

        digits_only = htsno.replace(".", "")

        # Chapter root: exactly 2 digits, e.g. "84"
        if htsno and len(digits_only) == 2 and digits_only.isdigit():
            current_chapter = {
                "code": digits_only,
                "description": description,
                "level": "chapter",
                "keywords": [],
                "legal_notes": [],
                "children": [],
            }
            chapters_by_code[digits_only] = current_chapter
            chapters_order.append(digits_only)
            current_heading = None
            continue

        # Heading: exactly 4 digits, e.g. "8471"
        if htsno and len(digits_only) == 4 and digits_only.isdigit():
            if current_chapter is None:
                # Defensive: some export ranges may start mid-chapter; synthesize
                # a chapter root from the heading's first 2 digits.
                chap_code = digits_only[:2]
                current_chapter = chapters_by_code.get(chap_code) or {
                    "code": chap_code,
                    "description": f"Chapter {chap_code}",
                    "level": "chapter",
                    "keywords": [],
                    "legal_notes": [],
                    "children": [],
                }
                chapters_by_code[chap_code] = current_chapter
                if chap_code not in chapters_order:
                    chapters_order.append(chap_code)

            current_heading = {
                "code": htsno,
                "description": description,
                "level": "heading",
                "keywords": [],
                "legal_notes": [],
                "children": [],
                "duty_rate": general,
            }
            current_chapter["children"].append(current_heading)
            continue

        # Everything with a real htsno deeper than 4 digits (6/8/10-digit) is a subheading
        if htsno and current_heading is not None:
            current_heading["children"].append(
                {
                    "code": htsno,
                    "description": description,
                    "level": "subheading",
                    "keywords": [],
                    "legal_notes": [],
                    "children": [],
                    "duty_rate": general,
                    "units": units,
                }
            )
            continue

        # Rows with NO htsno (pure descriptive text, e.g. "Live animals:") but
        # a current heading in progress: fold their words into the heading's
        # own description/keywords so they still contribute to lexical matching,
        # since the GRI engine scores off description + keyword text.
        if current_heading is not None:
            current_heading["keywords"].append(description)
        elif current_chapter is not None:
            current_chapter["keywords"].append(description)

    return {"chapters": [chapters_by_code[c] for c in chapters_order]}


def main():
    raw = fetch_raw_hts()
    tree = build_tree(raw)

    n_chapters = len(tree["chapters"])
    n_headings = sum(len(c["children"]) for c in tree["chapters"])
    n_subheadings = sum(len(h["children"]) for c in tree["chapters"] for h in c["children"])

    print(f"Built tree: {n_chapters} chapters, {n_headings} headings, {n_subheadings} subheadings.")

    if n_chapters < 90:
        print("\nWARNING: fewer than 90 chapters were parsed. This usually means the")
        print("field-name assumptions in this script (FIELD_HTSNO etc.) don't match")
        print("what the live API actually returned. Re-check the printed key list above")
        print("and let's fix the parser together before trusting this output.\n")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2)

    print(f"\nWrote full HTS dataset to: {OUTPUT_PATH}")
    print("Next: point the server at it (it's the default path in server_fastapi/main.py)")
    print("and restart uvicorn, or run:")
    print("  python3 -m unittest tests.test_gri_engine -v  # sanity check the engine still passes")


if __name__ == "__main__":
    main()
