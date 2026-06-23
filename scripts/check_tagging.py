#!/usr/bin/env python3
"""Validate an agent-produced product attribute file."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from build_pivot_table import (
    dimension_contract,
    extract_products,
    normalized_tag_rows,
    read_json,
    validate_tagging,
)


def validate_without_schema(products, tagged, max_unknown_ratio):
    """Validate tagging completeness without a dimension schema."""
    errors = []
    warnings = []
    source_asins = {item["asin"] for item in products}
    tagged_asins = {item["asin"] for item in tagged}

    missing = source_asins - tagged_asins
    extra = tagged_asins - source_asins
    if missing:
        errors.append(f"Missing tagged ASINs: {sorted(missing)[:5]}")
    if extra:
        warnings.append(f"Extra tagged ASINs not in source: {sorted(extra)[:5]}")

    # Count unknown values across all dimensions
    dims = set()
    for item in tagged:
        for key in list(item.keys()):
            if key != "asin":
                dims.add(key)

    unknown_ratios = {}
    for dim in sorted(dims):
        values = [item.get(dim, "unknown") for item in tagged]
        total = len(values)
        unknown_count = values.count("unknown") + values.count(None) + values.count("")
        unknown_ratios[dim] = round(unknown_count / total, 2) if total else 0

    over_threshold = {k: v for k, v in unknown_ratios.items() if v > max_unknown_ratio}
    if over_threshold:
        errors.append(f"Unknown ratio exceeds {max_unknown_ratio}: {over_threshold}")

    return {
        "schema_version": 1,
        "valid": not errors,
        "source_products": len(products),
        "tagged_products": len(tagged),
        "dimensions": sorted(dims),
        "unknown_ratios": unknown_ratios,
        "errors": errors,
        "warnings": warnings,
        "tagging_source": "ai_discovery",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--tagged-json", type=Path, required=True)
    parser.add_argument("--dimensions-file", type=Path, required=False)
    parser.add_argument("--price-unit", choices=("usd", "cents"), required=True)
    parser.add_argument("--max-unknown-ratio", type=float, default=0.65)
    args = parser.parse_args()

    products = extract_products(args.input, args.price_unit)
    tagged = normalized_tag_rows(read_json(args.tagged_json))

    if args.dimensions_file:
        _, allowed = dimension_contract(args.dimensions_file)
        result = validate_tagging(products, tagged, allowed, args.max_unknown_ratio)
        result["tagging_source"] = "confirmed_schema"
    else:
        result = validate_without_schema(products, tagged, args.max_unknown_ratio)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
