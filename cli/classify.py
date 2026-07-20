#!/usr/bin/env python3
"""
SYJ OpenTrade Logic - CLI
Usage:
    python3 cli/classify.py "cotton knitted t-shirt for men"
    python3 cli/classify.py "cordless electric drill" --json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gri_engine import GRIEngine  # noqa: E402


def _default_data_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "data", "hts_sample.json")


def print_human(result_dict: dict) -> None:
    print(f"\nProduct: {result_dict['product_description']}")
    if not result_dict["is_classified"]:
        print(f"  UNRESOLVED: {result_dict['unresolved_reason']}")
        return

    print(f"  HTS Code   : {result_dict['final_code']}")
    print(f"  Description: {result_dict['final_description']}")
    print(f"  Confidence : {result_dict['confidence']}")
    print(f"  Duty Rate  : {result_dict['duty_rate']}")
    print("  Decision Path:")
    for step in result_dict["decision_path"]:
        print(f"    - [{step['rule_applied']}] {step['node_code']}: {step['reasoning']}")
    if result_dict["alternatives"]:
        print("  Alternatives considered:")
        for alt in result_dict["alternatives"]:
            print(f"    - {alt['code']} ({alt['confidence']}): {alt['reason_not_selected']}")
    if result_dict["supporting_notes"]:
        print("  Supporting Notes:")
        for note in result_dict["supporting_notes"]:
            print(f"    - {note}")


def main():
    parser = argparse.ArgumentParser(description="SYJ OpenTrade Logic classifier")
    parser.add_argument("description", help="Product description to classify")
    parser.add_argument("--data", default=_default_data_path(), help="Path to HTS JSON dataset")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    engine = GRIEngine(args.data)
    result = engine.classify(args.description)
    result_dict = result.to_dict()

    if args.json:
        print(json.dumps(result_dict, indent=2))
    else:
        print_human(result_dict)


if __name__ == "__main__":
    main()
