#!/usr/bin/env python3
"""Normalize review responses into an evidence-addressable VOC bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ALIASES = {
    "review_id": ("ReviewId", "review_id", "Id", "id"),
    "asin": ("Asin", "ASIN", "asin"),
    "rating": ("Star", "Rating", "rating", "Score"),
    "title": ("Title", "title", "ReviewTitle"),
    "body": ("Content", "Body", "Text", "content", "body", "text"),
    "date": ("Date", "CreateTime", "date", "created_at"),
}


def value(record: dict[str, Any], name: str) -> Any:
    lowered = {str(key).lower(): item for key, item in record.items()}
    for alias in ALIASES[name]:
        if alias in record:
            return record[alias]
        if alias.lower() in lowered:
            return lowered[alias.lower()]
    return None


def looks_like_reviews(items: Any) -> bool:
    if not isinstance(items, list) or not items:
        return False
    sample = [item for item in items[:5] if isinstance(item, dict)]
    return bool(
        sample
        and any(value(item, "body") or value(item, "rating") for item in sample)
    )


def find_reviews(payload: Any) -> list[dict[str, Any]]:
    if looks_like_reviews(payload):
        return payload
    if isinstance(payload, dict):
        for key in ("Reviews", "reviews", "Items", "items", "List", "list"):
            if key in payload and looks_like_reviews(payload[key]):
                return payload[key]
        for item in payload.values():
            found = find_reviews(item)
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = find_reviews(item)
            if found:
                return found
    return []


def number(raw: Any) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def evidence_id(asin: str, review_id: str, body: str) -> str:
    digest = hashlib.sha256(f"{asin}|{review_id}|{body}".encode("utf-8")).hexdigest()
    return f"rev-{digest[:12]}"


def normalize(inputs: list[Path], default_asin: str = "") -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    warnings: list[str] = []
    for path in inputs:
        payload = json.loads(path.read_text(encoding="utf-8"))
        reviews = find_reviews(payload)
        if not reviews:
            warnings.append(f"No reviews found in {path}")
            continue
        for raw in reviews:
            body = str(value(raw, "body") or "").strip()
            title = str(value(raw, "title") or "").strip()
            asin = str(value(raw, "asin") or default_asin).strip()
            review_id = str(value(raw, "review_id") or "").strip()
            rating = number(value(raw, "rating"))
            if not body and not title:
                continue
            key = evidence_id(asin, review_id, f"{title}|{body}")
            if key in seen:
                continue
            seen.add(key)
            polarity = (
                "negative"
                if rating is not None and rating <= 3
                else "positive"
                if rating is not None and rating >= 4
                else "unknown"
            )
            records.append(
                {
                    "evidence_id": key,
                    "asin": asin,
                    "review_id": review_id,
                    "rating": rating,
                    "polarity": polarity,
                    "title": title,
                    "body": body,
                    "date": str(value(raw, "date") or ""),
                    "source_file": str(path),
                }
            )
    return {
        "schema_version": 1,
        "records": records,
        "counts": {
            "total": len(records),
            "positive": sum(item["polarity"] == "positive" for item in records),
            "negative": sum(item["polarity"] == "negative" for item in records),
            "unknown": sum(item["polarity"] == "unknown" for item in records),
        },
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a review-insight bundle")
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--asin", default="")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = normalize(args.input, args.asin)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result["counts"], ensure_ascii=False))
    return 0 if result["records"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
