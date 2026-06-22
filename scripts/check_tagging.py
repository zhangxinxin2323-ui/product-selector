#!/usr/bin/env python3
"""Validate an agent-produced product attribute file against confirmed rules."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_pivot_table import (
    dimension_contract,
    extract_products,
    normalized_tag_rows,
    read_json,
    validate_tagging,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--tagged-json", type=Path, required=True)
    parser.add_argument("--dimensions-file", type=Path, required=True)
    parser.add_argument("--price-unit", choices=("usd", "cents"), required=True)
    parser.add_argument("--max-unknown-ratio", type=float, default=0.65)
    args = parser.parse_args()

    products = extract_products(args.input, args.price_unit)
    tagged = normalized_tag_rows(read_json(args.tagged_json))
    _, allowed = dimension_contract(args.dimensions_file)
    result = validate_tagging(
        products, tagged, allowed, args.max_unknown_ratio
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
