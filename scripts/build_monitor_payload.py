#!/usr/bin/env python3
"""Build a dry-run-safe monitoring record from ProductRequest data."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALIASES = {
    "asin": ("Asin", "ASIN", "asin"),
    "price": ("Price", "price", "BuyBoxPrice"),
    "bsr": ("Bsr", "BSR", "BsrRank", "SalesRank"),
    "rating": ("Ratings", "Rating", "rating"),
    "reviews": ("RatingsCount", "ReviewCount", "reviews"),
}


def field(payload: Any, name: str) -> Any:
    if isinstance(payload, dict):
        lowered = {str(key).lower(): value for key, value in payload.items()}
        for alias in ALIASES[name]:
            if alias in payload:
                return payload[alias]
            if alias.lower() in lowered:
                return lowered[alias.lower()]
        for value in payload.values():
            found = field(value, name)
            if found not in (None, ""):
                return found
    if isinstance(payload, list):
        for value in payload:
            found = field(value, name)
            if found not in (None, ""):
                return found
    return None


def number(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return None


def build(
    payload: dict[str, Any],
    analysis_key: str,
    domain: int,
    frequency: str,
    linked_record_id: str,
    price_unit: str,
) -> dict[str, Any]:
    asin = str(field(payload, "asin") or "").strip()
    if not asin:
        raise ValueError("ProductRequest payload does not contain an ASIN")
    price = number(field(payload, "price"))
    if price is not None and price_unit == "cents":
        price /= 100
    fields = {
        "ASIN": asin,
        "站点": domain,
        "追踪频率": frequency,
        "初始售价": round(price, 2) if price is not None else None,
        "初始BSR": field(payload, "bsr"),
        "初始评分": number(field(payload, "rating")),
        "初始评论数": number(field(payload, "reviews")),
        "初始抓取时间": datetime.now(timezone.utc).isoformat(),
        "关联分析键": analysis_key,
        "关联选品开发记录ID": linked_record_id or None,
        "监控状态": "待启用",
    }
    missing = [name for name, value in fields.items() if value in (None, "")]
    return {
        "schema_version": 1,
        "operation": "upsert",
        "idempotency_key": f"{domain}:asin:{asin}",
        "fields": fields,
        "missing_fields": missing,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build monitoring upsert payload")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--analysis-key", required=True)
    parser.add_argument("--domain", type=int, default=1)
    parser.add_argument("--frequency", default="daily")
    parser.add_argument("--linked-record-id", default="")
    parser.add_argument("--price-unit", choices=("usd", "cents"), default="usd")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = build(
            json.loads(args.input.read_text(encoding="utf-8")),
            args.analysis_key,
            args.domain,
            args.frequency,
            args.linked_record_id,
            args.price_unit,
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
