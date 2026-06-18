#!/usr/bin/env python3
"""Tag Amazon products with configurable dimensions and build cross matrices.

The engine is category-agnostic. Category knowledge lives in JSON dimension
files under references/dimensions. When no confirmed dimension file is given,
the script uses the generic library and writes a draft for human confirmation.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations, product
from pathlib import Path
from typing import Any, Iterable


FIELD_ALIASES = {
    "asin": ("Asin", "ASIN", "asin"),
    "title": ("Title", "title", "ProductTitle", "product_title"),
    "description": ("Description", "description", "Feature", "BulletPoints"),
    "brand": ("Brand", "brand"),
    "price": ("Price", "price", "BuyBoxPrice"),
    "sales": ("SalesVolumeOfMonth", "MonthlySales", "sales", "monthly_sales"),
    "revenue": ("SalesAmountOfMonth", "MonthlyRevenue", "revenue"),
    "ratings_count": ("RatingsCount", "ReviewCount", "ratings_count"),
    "rating": ("Ratings", "Rating", "rating"),
    "online_days": ("OnlineDays", "online_days"),
    "is_fba": ("IsFBA", "is_fba"),
}

DEFAULT_STOPWORDS = {
    "amazon",
    "and",
    "best",
    "black",
    "compatible",
    "for",
    "from",
    "high",
    "new",
    "of",
    "pack",
    "portable",
    "premium",
    "professional",
    "set",
    "the",
    "with",
}

SPEC_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(inch|inches|in|ft|feet|w|watt|watts|v|volt|volts|"
    r"mah|ah|oz|lb|lbs|gallon|gallons|pack|pcs|piece|pieces|tier|tiers|port|ports)\b",
    re.IGNORECASE,
)
TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)?", re.IGNORECASE)


@dataclass(frozen=True)
class Rule:
    value: str
    patterns: tuple[str, ...]
    excludes: tuple[str, ...] = ()


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(safe_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(safe_text(item) for item in value.values())
    return str(value).strip()


def safe_number(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y", "fba"}


def field(record: dict[str, Any], name: str) -> Any:
    for alias in FIELD_ALIASES[name]:
        if alias in record:
            return record[alias]
    lowered = {str(key).lower(): value for key, value in record.items()}
    for alias in FIELD_ALIASES[name]:
        if alias.lower() in lowered:
            return lowered[alias.lower()]
    return None


def looks_like_product_list(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    sample = [item for item in value[:5] if isinstance(item, dict)]
    if not sample:
        return False
    hits = 0
    for item in sample:
        keys = {str(key).lower() for key in item}
        if keys.intersection({"asin", "title", "producttitle"}):
            hits += 1
    return hits >= max(1, math.ceil(len(sample) / 2))


def find_products(payload: Any) -> list[dict[str, Any]]:
    if looks_like_product_list(payload):
        return payload
    if isinstance(payload, dict):
        preferred = ("Products", "products", "Items", "items", "Results", "results")
        for key in preferred:
            if key in payload and looks_like_product_list(payload[key]):
                return payload[key]
        for value in payload.values():
            found = find_products(value)
            if found:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = find_products(value)
            if found:
                return found
    return []


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("-", " ")).strip()


def pattern_matches(pattern: str, text: str) -> bool:
    if pattern.startswith("re:"):
        return re.search(pattern[3:], text, flags=re.IGNORECASE) is not None
    literal = normalized(pattern)
    return re.search(rf"(?<!\w){re.escape(literal)}(?!\w)", normalized(text)) is not None


def rule_matches(rule: Rule, text: str) -> bool:
    if any(pattern_matches(item, text) for item in rule.excludes):
        return False
    return any(pattern_matches(item, text) for item in rule.patterns)


def parse_dimension_rules(raw_dimensions: dict[str, Any]) -> dict[str, list[Rule]]:
    parsed: dict[str, list[Rule]] = {}
    for dimension, spec in raw_dimensions.items():
        values = spec.get("values", spec) if isinstance(spec, dict) else spec
        rules: list[Rule] = []
        if isinstance(values, dict):
            for value, patterns in values.items():
                if isinstance(patterns, str):
                    patterns = [patterns]
                rules.append(Rule(str(value), tuple(str(item) for item in patterns)))
        elif isinstance(values, list):
            for item in values:
                if isinstance(item, str):
                    rules.append(Rule(item, (item,)))
                    continue
                if not isinstance(item, dict) or "name" not in item:
                    raise ValueError(f"Invalid rule in dimension {dimension!r}: {item!r}")
                patterns = item.get("patterns", [item["name"]])
                excludes = item.get("excludes", [])
                rules.append(
                    Rule(
                        str(item["name"]),
                        tuple(str(pattern) for pattern in patterns),
                        tuple(str(pattern) for pattern in excludes),
                    )
                )
        if rules:
            parsed[str(dimension)] = rules
    return parsed


def load_dimension_file(path: Path) -> tuple[dict[str, list[Rule]], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError(f"Unsupported dimension schema in {path}")
    dimensions = parse_dimension_rules(payload.get("dimensions", {}))
    if not dimensions:
        raise ValueError(f"No dimensions found in {path}")
    return dimensions, payload


def document_frequency(titles: Iterable[str], ngram_size: int) -> Counter[str]:
    counter: Counter[str] = Counter()
    for title in titles:
        tokens = [
            token
            for token in TOKEN_PATTERN.findall(normalized(title))
            if len(token) > 2 and token not in DEFAULT_STOPWORDS and not token.isdigit()
        ]
        ngrams = {
            " ".join(tokens[index : index + ngram_size])
            for index in range(max(0, len(tokens) - ngram_size + 1))
        }
        counter.update(ngrams)
    return counter


def discover_dimension_draft(
    titles: list[str], min_coverage: float, max_candidates: int
) -> dict[str, Any]:
    total = max(1, len(titles))
    minimum = max(2, math.ceil(total * min_coverage))
    maximum = max(minimum, math.floor(total * 0.75))

    feature_candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for size in (3, 2, 1):
        for term, count in document_frequency(titles, size).most_common():
            if count < minimum or count > maximum:
                continue
            if any(term in existing or existing in term for existing in seen):
                continue
            seen.add(term)
            feature_candidates.append(
                {
                    "name": re.sub(r"[^a-z0-9]+", "-", term).strip("-"),
                    "patterns": [term],
                    "coverage": round(count / total, 3),
                }
            )
            if len(feature_candidates) >= max_candidates:
                break
        if len(feature_candidates) >= max_candidates:
            break

    specs: dict[str, Counter[str]] = defaultdict(Counter)
    for title in titles:
        per_title: dict[str, set[str]] = defaultdict(set)
        for number, unit in SPEC_PATTERN.findall(title):
            canonical_unit = unit.lower().rstrip("s")
            per_title[canonical_unit].add(f"{number} {canonical_unit}")
        for unit, values in per_title.items():
            specs[unit].update(values)

    dimensions: dict[str, Any] = {}
    for unit, values in specs.items():
        frequent = [
            {"name": value, "patterns": [value], "coverage": round(count / total, 3)}
            for value, count in values.most_common()
            if count >= minimum
        ]
        if len(frequent) >= 2:
            dimensions[f"spec_{unit}"] = {"values": frequent}

    if len(feature_candidates) >= 2:
        dimensions["candidate_feature"] = {"values": feature_candidates}

    return {
        "schema_version": 1,
        "status": "draft",
        "name": "auto-discovered",
        "generated_from": {
            "products": len(titles),
            "minimum_coverage": min_coverage,
        },
        "dimensions": dimensions,
        "instructions": (
            "Review names, merge synonyms, remove category nouns, then change status "
            "to confirmed before using blank combinations for decisions."
        ),
    }


def detect_price_divisor(records: list[dict[str, Any]], price_unit: str) -> float:
    if price_unit == "usd":
        return 1.0
    if price_unit == "cents":
        return 100.0
    values = [safe_number(field(record, "price")) for record in records]
    values = [value for value in values if value > 0]
    if not values:
        return 1.0
    integer_ratio = sum(value.is_integer() for value in values) / len(values)
    median = statistics.median(values)
    return 100.0 if integer_ratio >= 0.8 and median >= 500 else 1.0


def normalize_products(
    records: list[dict[str, Any]], price_unit: str
) -> list[dict[str, Any]]:
    divisor = detect_price_divisor(records, price_unit)
    products: list[dict[str, Any]] = []
    for record in records:
        price = safe_number(field(record, "price")) / divisor
        sales = int(safe_number(field(record, "sales")))
        revenue = safe_number(field(record, "revenue"))
        if not revenue and price and sales:
            revenue = price * sales
        products.append(
            {
                "asin": safe_text(field(record, "asin")),
                "title": safe_text(field(record, "title")),
                "description": safe_text(field(record, "description")),
                "brand": safe_text(field(record, "brand")) or "unknown",
                "price": round(price, 2),
                "sales": sales,
                "revenue": round(revenue, 2),
                "ratings_count": int(safe_number(field(record, "ratings_count"))),
                "rating": safe_number(field(record, "rating")),
                "online_days": int(safe_number(field(record, "online_days"), 9999)),
                "is_fba": safe_bool(field(record, "is_fba")),
            }
        )
    return products


def tag_products(
    products: list[dict[str, Any]], dimensions: dict[str, list[Rule]]
) -> tuple[list[dict[str, Any]], dict[str, Counter[str]], dict[str, float]]:
    tagged: list[dict[str, Any]] = []
    distributions: dict[str, Counter[str]] = {
        dimension: Counter() for dimension in dimensions
    }
    matched_counts: Counter[str] = Counter()

    for product_record in products:
        item = dict(product_record)
        confidence: dict[str, str] = {}
        for dimension, rules in dimensions.items():
            value = "unknown"
            level = "unknown"
            for rule in rules:
                if rule_matches(rule, product_record["title"]):
                    value, level = rule.value, "high"
                    break
            if level == "unknown":
                for rule in rules:
                    if rule_matches(rule, product_record["description"]):
                        value, level = rule.value, "medium"
                        break
            item[dimension] = value
            confidence[dimension] = level
            distributions[dimension][value] += 1
            if value != "unknown":
                matched_counts[dimension] += 1
        item["attribute_confidence"] = confidence
        tagged.append(item)

    total = max(1, len(tagged))
    coverage = {
        dimension: round(matched_counts[dimension] / total, 3)
        for dimension in dimensions
    }
    return tagged, distributions, coverage


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))
    return ordered[index]


def choose_pairs(
    dimensions: dict[str, list[Rule]],
    coverage: dict[str, float],
    configured_pairs: list[list[str]],
    max_pairs: int,
) -> list[tuple[str, str]]:
    valid_configured = [
        (pair[0], pair[1])
        for pair in configured_pairs
        if len(pair) == 2 and pair[0] in dimensions and pair[1] in dimensions
    ]
    if valid_configured:
        return valid_configured[:max_pairs]

    eligible = [
        name
        for name, rules in dimensions.items()
        if coverage.get(name, 0) >= 0.1 and 2 <= len(rules) <= 12
    ]
    eligible.sort(key=lambda name: (-coverage.get(name, 0), len(dimensions[name])))
    return list(combinations(eligible, 2))[:max_pairs]


def cell_metrics(items: list[dict[str, Any]]) -> dict[str, Any]:
    sales = sum(item["sales"] for item in items)
    revenue = sum(item["revenue"] for item in items)
    prices = [item["price"] for item in items if item["price"] > 0]
    reviews = [item["ratings_count"] for item in items]
    brand_sales: Counter[str] = Counter()
    for item in items:
        brand_sales[item["brand"]] += item["sales"]
    top3_sales = sum(value for _, value in brand_sales.most_common(3))
    concentration = top3_sales / sales if sales else 0.0
    return {
        "count": len(items),
        "sales": sales,
        "revenue": round(revenue, 2),
        "avg_price": round(statistics.mean(prices), 2) if prices else 0.0,
        "avg_reviews": round(statistics.mean(reviews), 1) if reviews else 0.0,
        "top3_brand_sales_share": round(concentration, 3),
    }


def build_cross_analysis(
    tagged: list[dict[str, Any]],
    dimensions: dict[str, list[Rule]],
    pairs: list[tuple[str, str]],
    dimensions_confirmed: bool,
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for left, right in pairs:
        left_values = [rule.value for rule in dimensions[left]]
        right_values = [rule.value for rule in dimensions[right]]
        cells: list[dict[str, Any]] = []
        for left_value, right_value in product(left_values, right_values):
            matches = [
                item
                for item in tagged
                if item.get(left) == left_value and item.get(right) == right_value
            ]
            metrics = cell_metrics(matches)
            cells.append(
                {
                    left: left_value,
                    right: right_value,
                    **metrics,
                }
            )

        nonzero_sales = [cell["sales"] for cell in cells if cell["count"] > 0]
        high_sales_threshold = percentile(nonzero_sales, 0.7)
        supplied_counts = [cell["count"] for cell in cells if cell["count"] > 0]
        low_count_threshold = percentile(supplied_counts, 0.3)

        for cell in cells:
            if cell["count"] == 0:
                cell["supply_status"] = "blank_unvalidated"
                cell["requires_demand_validation"] = True
                cell["demand_evidence"] = "none"
            elif (
                cell["sales"] >= high_sales_threshold
                and cell["count"] <= max(2, low_count_threshold)
            ):
                cell["supply_status"] = "high_demand_low_supply"
                cell["requires_demand_validation"] = False
                cell["demand_evidence"] = "observed_sales"
            elif cell["count"] <= 2:
                cell["supply_status"] = "scarce"
                cell["requires_demand_validation"] = True
                cell["demand_evidence"] = "none"
            else:
                cell["supply_status"] = "supplied"
                cell["requires_demand_validation"] = False
                cell["demand_evidence"] = "observed_sales"
            cell["opportunity_candidate"] = bool(
                dimensions_confirmed
                and cell["supply_status"] == "high_demand_low_supply"
            )

        output[f"{left}_x_{right}"] = {
            "dimensions": [left, right],
            "decision_eligible": dimensions_confirmed,
            "decision_blockers": (
                [] if dimensions_confirmed else ["dimensions_not_confirmed"]
            ),
            "cells": cells,
        }
    return output


def basic_stats(tagged: list[dict[str, Any]]) -> dict[str, Any]:
    total = max(1, len(tagged))
    prices = [item["price"] for item in tagged if item["price"] > 0]
    reviews = [item["ratings_count"] for item in tagged]
    brands = Counter(item["brand"] for item in tagged)
    return {
        "products": len(tagged),
        "new_products": {
            "up_to_90_days": sum(item["online_days"] <= 90 for item in tagged),
            "91_to_180_days": sum(90 < item["online_days"] <= 180 for item in tagged),
            "181_to_365_days": sum(180 < item["online_days"] <= 365 for item in tagged),
            "over_365_days": sum(item["online_days"] > 365 for item in tagged),
        },
        "new_ratio_180_days": round(
            sum(item["online_days"] <= 180 for item in tagged) / total, 3
        ),
        "price": {
            "min": round(min(prices), 2) if prices else 0.0,
            "max": round(max(prices), 2) if prices else 0.0,
            "mean": round(statistics.mean(prices), 2) if prices else 0.0,
            "median": round(statistics.median(prices), 2) if prices else 0.0,
        },
        "reviews_mean": round(statistics.mean(reviews), 1) if reviews else 0.0,
        "brand_count": len(brands),
        "top_brands_by_product_count": brands.most_common(10),
        "fba_rate": round(sum(item["is_fba"] for item in tagged) / total, 3),
    }


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Configurable Top100 attribute tagging and cross analysis"
    )
    parser.add_argument("--input", type=Path, help="Input JSON; defaults to stdin")
    parser.add_argument("--dimensions-file", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    parser.add_argument(
        "--price-unit", choices=("auto", "usd", "cents"), default="auto"
    )
    parser.add_argument("--min-coverage", type=float, default=0.1)
    parser.add_argument("--max-candidates", type=int, default=12)
    parser.add_argument("--max-pairs", type=int, default=3)
    parser.add_argument("--json-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw = (
        args.input.read_text(encoding="utf-8")
        if args.input
        else sys.stdin.read()
    )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"Invalid JSON: {exc}"}), file=sys.stderr)
        return 2

    raw_products = find_products(payload)
    if not raw_products:
        print(json.dumps({"error": "No product list found"}), file=sys.stderr)
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    products = normalize_products(raw_products, args.price_unit)
    titles = [item["title"] for item in products]

    dimension_source = "confirmed"
    draft: dict[str, Any] | None = None
    if args.dimensions_file:
        dimensions, dimension_meta = load_dimension_file(args.dimensions_file)
        if dimension_meta.get("status") != "confirmed":
            dimension_source = "draft"
    else:
        generic_path = (
            Path(__file__).resolve().parent.parent
            / "references"
            / "dimensions"
            / "generic.json"
        )
        dimensions, dimension_meta = load_dimension_file(generic_path)
        dimension_source = "generic_plus_draft"
        draft = discover_dimension_draft(
            titles, args.min_coverage, args.max_candidates
        )
        write_json(args.output_dir / "dimension-draft.json", draft)

    tagged, distributions, coverage = tag_products(products, dimensions)
    pairs = choose_pairs(
        dimensions,
        coverage,
        dimension_meta.get("cross_pairs", []),
        args.max_pairs,
    )
    dimensions_confirmed = dimension_source == "confirmed"
    cross = build_cross_analysis(
        tagged, dimensions, pairs, dimensions_confirmed=dimensions_confirmed
    )
    uncertain = [
        {
            "asin": item["asin"],
            "title": item["title"],
            "unknown_dimensions": [
                dimension
                for dimension in dimensions
                if item.get(dimension) == "unknown"
            ],
        }
        for item in tagged
        if any(item.get(dimension) == "unknown" for dimension in dimensions)
    ]

    summary = {
        "schema_version": 1,
        "dimension_source": dimension_source,
        "requires_dimension_confirmation": not dimensions_confirmed,
        "decision_eligible": dimensions_confirmed,
        "decision_blockers": (
            [] if dimensions_confirmed else ["dimensions_not_confirmed"]
        ),
        "dimension_coverage": coverage,
        "attribute_distribution": {
            dimension: dict(counts)
            for dimension, counts in distributions.items()
        },
        "cross_analysis": cross,
        "stats": basic_stats(tagged),
        "warnings": [
            "Blank combinations are supply observations, not proven demand.",
            "Use --price-unit explicitly for high-ticket categories when auto is ambiguous.",
        ],
    }

    write_json(args.output_dir / "top100_parsed.json", tagged)
    write_json(args.output_dir / "attribute_summary.json", summary)
    write_json(args.output_dir / "cross_analysis.json", cross)
    write_json(args.output_dir / "uncertain_products.json", uncertain)

    if args.json_only:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(
            f"Tagged {len(tagged)} products across {len(dimensions)} dimensions; "
            f"{len(pairs)} cross matrices written to {args.output_dir}."
        )
        if summary["requires_dimension_confirmation"]:
            print(
                "Dimension confirmation required before treating blank combinations "
                "as decision evidence."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
