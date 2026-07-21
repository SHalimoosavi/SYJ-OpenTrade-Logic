#!/usr/bin/env python3
"""
SYJ OpenTrade Logic - Full HTS dataset importer
==================================================
Pulls the REAL, current, full Harmonized Tariff Schedule (chapters 01-99,
~17,000+ line items) from the official USITC REST API and converts it into
the nested chapter -> heading -> subheading JSON tree our GRIEngine expects
(same shape as data/hts_sample.json).
"""

import json
import os
import sys
import urllib.request
import urllib.error

EXPORT_URL = "https://hts.usitc.gov/reststop/exportList?from=0101&to=9999&format=JSON&styles=false"
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "hts_full.json")

FIELD_HTSNO = "htsno"
FIELD_DESCRIPTION = "description"
FIELD_INDENT = "indent"
FIELD_GENERAL = "general"
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
        sys.exit(1)

    data = json.loads(raw_bytes)
    if isinstance(data, dict) and "results" in data:
        data = data["results"]
    if not isinstance(data, list) or not data:
        print("ERROR: unexpected response shape from USITC API.")
        sys.exit(1)

    print(f"Fetched {len(data)} raw records.\n")
    print("First record's keys:")
    print(f"  {sorted(data[0].keys())}\n")
    return data


def _safe_int(raw_value, default: int = 0) -> int:
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default


def build_tree(raw_records: list) -> dict:
    """
    Convert the USITC flat, indent-based record list into our nested
    chapter -> heading -> subheading tree, respecting the real nesting
    depth encoded in the `indent` field.

    Chapter membership is derived from each heading/subheading's OWN code
    prefix, not from waiting for a dedicated 2-digit chapter row (the real
    feed emits very few of those).

    Loose grouping rows ("Other:", "Women's or girls':", "Of cotton:") are
    tracked on an indent-keyed stack so their text only attaches to the
    specific branch nested beneath them -- not the whole heading.

    Chapter 99 entries with no real 4-digit heading parent get a
    synthesized placeholder heading (marked so GRIEngine can deprioritize
    it), rather than being misread as a real heading.
    """
    chapter_titles = {}
    for rec in raw_records:
        htsno = (rec.get(FIELD_HTSNO) or "").strip()
        description = (rec.get(FIELD_DESCRIPTION) or "").strip()
        digits_only = htsno.replace(".", "")
        if htsno and len(digits_only) == 2 and digits_only.isdigit() and description:
            chapter_titles.setdefault(digits_only, description)

    chapters_by_code = {}
    chapters_order = []
    current_chapter = None
    current_heading = None
    context_stack = []

    def get_or_create_chapter(chap_code: str) -> dict:
        nonlocal current_chapter
        if chap_code not in chapters_by_code:
            chapters_by_code[chap_code] = {
                "code": chap_code,
                "description": chapter_titles.get(chap_code, f"Chapter {chap_code}"),
                "level": "chapter",
                "keywords": [],
                "legal_notes": [],
                "children": [],
            }
            chapters_order.append(chap_code)
        current_chapter = chapters_by_code[chap_code]
        return current_chapter

    def context_chain_text(indent: int) -> list:
        return [text for (lvl, text) in context_stack if lvl < indent]

    for rec in raw_records:
        htsno = (rec.get(FIELD_HTSNO) or "").strip()
        description = (rec.get(FIELD_DESCRIPTION) or "").strip()
        general = (rec.get(FIELD_GENERAL) or "").strip() or None
        units = rec.get(FIELD_UNITS) or []
        indent = _safe_int(rec.get(FIELD_INDENT), default=0)

        if not description:
            continue

        digits_only = htsno.replace(".", "")

        if htsno and len(digits_only) == 2 and digits_only.isdigit():
            get_or_create_chapter(digits_only)
            current_chapter["description"] = description
            current_heading = None
            context_stack = []
            continue

        if htsno and len(digits_only) == 4 and digits_only.isdigit():
            chap_code = digits_only[:2]
            if current_chapter is None or current_chapter["code"] != chap_code:
                get_or_create_chapter(chap_code)

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
            context_stack = []
            continue

        if htsno and len(digits_only) > 4:
            chap_code = digits_only[:2]
            if current_chapter is None or current_chapter["code"] != chap_code:
                get_or_create_chapter(chap_code)
                current_heading = None
                context_stack = []

            if current_heading is None or current_heading["code"] != digits_only[:4]:
                synthetic_code = digits_only[:4] if len(digits_only) >= 4 else chap_code
                current_heading = {
                    "code": synthetic_code,
                    "description": f"[Ungrouped entries under chapter {chap_code}]",
                    "level": "heading",
                    "keywords": [],
                    "legal_notes": [],
                    "children": [],
                    "duty_rate": None,
                }
                current_chapter["children"].append(current_heading)
                context_stack = []

            ancestor_text = context_chain_text(indent)

            subheading_node = {
                "code": htsno,
                "description": description,
                "level": "subheading",
                "keywords": ancestor_text,
                "legal_notes": [],
                "children": [],
                "duty_rate": general,
                "units": units,
            }
            current_heading["children"].append(subheading_node)
            context_stack = [(lvl, t) for (lvl, t) in context_stack if lvl < indent]
            context_stack.append((indent, description))
            continue

        context_stack = [(lvl, t) for (lvl, t) in context_stack if lvl < indent]
        context_stack.append((indent, description))

    return {"chapters": [chapters_by_code[c] for c in chapters_order]}


def main():
    raw = fetch_raw_hts()
    tree = build_tree(raw)

    n_chapters = len(tree["chapters"])
    n_headings = sum(len(c["children"]) for c in tree["chapters"])
    n_subheadings = sum(len(h["children"]) for c in tree["chapters"] for h in c["children"])

    print(f"Built tree: {n_chapters} chapters, {n_headings} headings, {n_subheadings} subheadings.")

    if n_chapters < 90:
        print("\nWARNING: fewer than 90 chapters were parsed.\n")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2)

    print(f"\nWrote full HTS dataset to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
