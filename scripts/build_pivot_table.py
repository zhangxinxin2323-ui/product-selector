#!/usr/bin/env python3
"""Build a validated, pivot-ready CSV from Sorftime category data.

Confirmed dimension files produce deterministic tags. Agent-produced tags are
accepted only when they pass the same versioned dimension contract.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
UNKNOWN_VALUES = {"", "unknown", "other", None}
BASE_COLUMNS = [
    ("ASIN", "asin"),
    ("品牌", "brand"),
    ("标题", "title"),
    ("售价($)", "price"),
    ("月销量", "sales"),
    ("评论数", "ratings_count"),
    ("评分", "rating"),
    ("上架天数", "online_days"),
    ("FBA", "is_fba"),
]


def load_attribute_engine():
    path = Path(__file__).with_name("attribute-tagger.py")
    spec = importlib.util.spec_from_file_location("product_selector_attribute_tagger", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load attribute engine: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ATTRIBUTE_ENGINE = load_attribute_engine()


def read_json(path: Path) -> Any:
    raw = path.read_text(encoding="utf-8-sig", errors="strict")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        for index, char in enumerate(raw):
            if char not in "[{":
                continue
            try:
                return json.loads(raw[index:])
            except json.JSONDecodeError:
                continue
        raise ValueError(f"No valid JSON found in {path}")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def extract_products(input_path: Path, price_unit: str) -> list[dict[str, Any]]:
    payload = read_json(input_path)
    records = ATTRIBUTE_ENGINE.find_products(payload)
    if not records:
        raise ValueError(f"No product list found in {input_path}")
    products = ATTRIBUTE_ENGINE.normalize_products(records, price_unit)
    asins = [item["asin"] for item in products]
    if not all(asins):
        raise ValueError("Every product must have an ASIN")
    duplicates = sorted(asin for asin, count in Counter(asins).items() if count > 1)
    if duplicates:
        raise ValueError(f"Duplicate ASINs in source: {duplicates[:5]}")
    return products


def dimension_contract(path: Path) -> tuple[dict[str, Any], dict[str, set[str]]]:
    payload = read_json(path)
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Unsupported dimension schema_version in {path}")
    if payload.get("status") != "confirmed":
        raise ValueError("Final tagging requires a confirmed dimension file")
    rules, _ = ATTRIBUTE_ENGINE.load_dimension_file(path)
    allowed = {
        name: {rule.value for rule in dimension_rules} | {"unknown"}
        for name, dimension_rules in rules.items()
    }
    return payload, allowed


def normalized_tag_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if payload.get("schema_version") not in (None, SCHEMA_VERSION):
            raise ValueError("Unsupported tagged payload schema_version")
        payload = payload.get("products", payload.get("data", []))
    if not isinstance(payload, list):
        raise ValueError("Tagged payload must contain a products array")
    if not all(isinstance(item, dict) for item in payload):
        raise ValueError("Every tagged product must be an object")
    return payload


def validate_tagging(
    products: list[dict[str, Any]],
    tagged: list[dict[str, Any]],
    allowed: dict[str, set[str]],
    max_unknown_ratio: float,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    expected = [item["asin"] for item in products]
    actual = [str(item.get("asin") or "") for item in tagged]
    counts = Counter(actual)

    duplicates = sorted(asin for asin, count in counts.items() if asin and count > 1)
    missing = sorted(set(expected) - set(actual))
    extras = sorted(set(actual) - set(expected) - {""})
    if "" in actual:
        errors.append("Every tagged product must have an ASIN")
    if duplicates:
        errors.append(f"Duplicate tagged ASINs: {duplicates[:5]}")
    if missing:
        errors.append(f"Missing tagged ASINs: {missing[:5]}")
    if extras:
        errors.append(f"Unexpected tagged ASINs: {extras[:5]}")

    invalid_values: list[dict[str, str]] = []
    unknown_counts = {dimension: 0 for dimension in allowed}
    for item in tagged:
        asin = str(item.get("asin") or "")
        for dimension, values in allowed.items():
            if dimension not in item:
                errors.append(f"{asin or '<missing>'} lacks dimension {dimension}")
                continue
            value = item.get(dimension)
            if value in UNKNOWN_VALUES:
                unknown_counts[dimension] += 1
                continue
            if not isinstance(value, str) or value not in values:
                invalid_values.append(
                    {"asin": asin, "dimension": dimension, "value": str(value)}
                )
    if invalid_values:
        errors.append(f"Invalid dimension values: {invalid_values[:5]}")

    total = max(1, len(products))
    unknown_ratios = {
        dimension: round(count / total, 3)
        for dimension, count in unknown_counts.items()
    }
    excessive = {
        dimension: ratio
        for dimension, ratio in unknown_ratios.items()
        if ratio > max_unknown_ratio
    }
    if excessive:
        errors.append(
            f"Unknown ratio exceeds {max_unknown_ratio:.0%}: {excessive}"
        )
    elif any(unknown_ratios.values()):
        warnings.append(f"Unknown values remain: {unknown_ratios}")

    return {
        "schema_version": SCHEMA_VERSION,
        "valid": not errors,
        "source_products": len(products),
        "tagged_products": len(tagged),
        "dimensions": sorted(allowed),
        "unknown_ratios": unknown_ratios,
        "errors": errors,
        "warnings": warnings,
    }


def merge_tags(
    products: list[dict[str, Any]], tagged: list[dict[str, Any]], dimensions: list[str]
) -> list[dict[str, Any]]:
    tags = {str(item["asin"]): item for item in tagged}
    merged: list[dict[str, Any]] = []
    for product in products:
        row = dict(product)
        for dimension in dimensions:
            row[dimension] = tags[product["asin"]].get(dimension, "unknown")
        merged.append(row)
    return merged


def write_pivot_csv(
    products: list[dict[str, Any]], dimensions: list[str], output_path: Path
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([label for label, _ in BASE_COLUMNS] + dimensions)
        for product in products:
            writer.writerow(
                [product.get(field, "") for _, field in BASE_COLUMNS]
                + [product.get(dimension, "unknown") for dimension in dimensions]
            )


def write_enrichment_queue(
    products: list[dict[str, Any]], dimensions: list[str], output_path: Path
) -> None:
    queue = []
    for product in products:
        unknown = [
            dimension
            for dimension in dimensions
            if product.get(dimension) in UNKNOWN_VALUES
        ]
        if unknown:
            queue.append(
                {
                    "asin": product["asin"],
                    "title": product["title"],
                    "unknown_dimensions": unknown,
                }
            )
    write_json(
        output_path,
        {"schema_version": SCHEMA_VERSION, "products": queue},
    )


def generate_prompt(
    products: list[dict[str, Any]], dimensions_path: Path | None, output_path: Path
) -> None:
    source_hash = hashlib.sha256(
        json.dumps(products, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    lines = [
        "# Product Selector attribute task",
        "",
        f"schema_version: {SCHEMA_VERSION}",
        f"source_sha256: {source_hash}",
        f"product_count: {len(products)}",
        "",
    ]
    if dimensions_path:
        contract, allowed = dimension_contract(dimensions_path)
        lines.extend(
            [
                "Use the confirmed dimensions exactly as written. Do not add or rename dimensions.",
                json.dumps(
                    {
                        "dimension_set": contract.get("name"),
                        "allowed_values": {
                            key: sorted(values) for key, values in allowed.items()
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            ]
        )
    else:
        lines.extend(
            [
                "Discover 5-8 purchase-decision dimensions.",
                "The output is a draft and is not decision-eligible until confirmed.",
            ]
        )
    lines.extend(
        [
            "",
            "Products:",
            json.dumps(
                [
                    {"asin": item["asin"], "title": item["title"]}
                    for item in products
                ],
                ensure_ascii=False,
                indent=2,
            ),
            "",
            "Return JSON only.",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--price-unit", choices=("usd", "cents"), required=True,
        help="Explicit Sorftime price unit; value-based guessing is forbidden.",
    )
    parser.add_argument("--dimensions-file", type=Path)
    parser.add_argument("--tagged-json", type=Path)
    parser.add_argument("--prompt-only", action="store_true")
    parser.add_argument("--max-unknown-ratio", type=float, default=0.65)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 0 <= args.max_unknown_ratio <= 1:
        raise ValueError("max-unknown-ratio must be between 0 and 1")
    products = extract_products(args.input, args.price_unit)

    if args.prompt_only:
        generate_prompt(products, args.dimensions_file, args.output)
        print(json.dumps({"prompt": str(args.output), "products": len(products)}))
        return 0
    if not args.dimensions_file:
        raise ValueError("--dimensions-file is required for final pivot output")

    dimension_meta, allowed = dimension_contract(args.dimensions_file)
    rules, _ = ATTRIBUTE_ENGINE.load_dimension_file(args.dimensions_file)
    if args.tagged_json:
        tagged = normalized_tag_rows(read_json(args.tagged_json))
        tagging_source = "agent"
    else:
        tagged, _, _ = ATTRIBUTE_ENGINE.tag_products(products, rules)
        tagging_source = "deterministic_rules"

    validation = validate_tagging(
        products, tagged, allowed, args.max_unknown_ratio
    )
    validation["tagging_source"] = tagging_source
    validation["dimension_set"] = dimension_meta.get("name")
    validation_path = args.output.with_name("tagging-validation.json")
    write_json(validation_path, validation)
    if not validation["valid"]:
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        return 2

    dimensions = list(allowed)
    merged = merge_tags(products, tagged, dimensions)
    write_json(
        args.output.with_name("tagged-products.json"),
        {
            "schema_version": SCHEMA_VERSION,
            "dimension_set": dimension_meta.get("name"),
            "tagging_source": tagging_source,
            "products": merged,
        },
    )
    write_pivot_csv(merged, dimensions, args.output)
    write_enrichment_queue(
        merged, dimensions, args.output.with_name("enrich-asins.json")
    )
    print(
        json.dumps(
            {
                "valid": True,
                "products": len(merged),
                "dimensions": dimensions,
                "pivot": str(args.output),
                "validation": str(validation_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
