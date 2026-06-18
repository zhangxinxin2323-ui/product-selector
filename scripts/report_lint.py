#!/usr/bin/env python3
"""Check report completeness without rewarding arbitrary line count."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_SECTIONS = {
    "executive_summary": r"(?im)^#{1,3}\s+.*(?:Executive Summary|执行摘要)",
    "market": r"(?im)^#{1,3}\s+.*(?:市场概况|关键词分析)",
    "competition": r"(?im)^#{1,3}\s+.*竞争格局",
    "attributes": r"(?im)^#{1,3}\s+.*属性",
    "cross_analysis": r"(?im)^#{1,3}\s+.*交叉分析",
    "voc": r"(?im)^#{1,3}\s+.*(?:VOC|消费者)",
    "opportunities": r"(?im)^#{1,3}\s+.*(?:供需缺口|机会)",
    "finance": r"(?im)^#{1,3}\s+.*财务",
    "barriers": r"(?im)^#{1,3}\s+.*(?:进入壁垒|风险)",
    "go_no_go": r"(?im)^#{1,3}\s+.*Go/No-Go",
    "product_matrix": r"(?im)^#{1,3}\s+.*产品矩阵",
    "sources": r"(?im)^#{1,3}\s+.*(?:数据来源|原始数据索引|证据索引)",
}

SOURCE_TOKENS = (
    "ProductRequest",
    "KeywordRequest",
    "CategoryRequest",
    "CategoryTrend",
)

PLACEHOLDER_PATTERNS = (
    r"\[(?:X|XX|待填|TODO|TBD)[^\]]*\]",
    r"<(?:ASIN|关键词|细分市场|N)>",
)


def lint(text: str) -> dict[str, object]:
    missing_sections = [
        name for name, pattern in REQUIRED_SECTIONS.items() if not re.search(pattern, text)
    ]
    source_hits = [token for token in SOURCE_TOKENS if token in text]
    placeholders = [
        match.group(0)
        for pattern in PLACEHOLDER_PATTERNS
        for match in re.finditer(pattern, text, flags=re.IGNORECASE)
    ]
    has_estimate_label = bool(re.search(r"(?:估算|假设|置信度|数据缺失)", text))
    errors: list[str] = []
    warnings: list[str] = []
    if missing_sections:
        errors.append(f"Missing report sections: {', '.join(missing_sections)}")
    if len(source_hits) < 3:
        errors.append("Fewer than three Sorftime source types are cited.")
    if placeholders:
        errors.append(f"Unresolved placeholders: {placeholders[:5]}")
    if not has_estimate_label:
        warnings.append("No estimate, assumption, confidence or missing-data label found.")
    decision_patterns = {
        "Market Decision": r"(?:Market Decision|Market GO|市场可行性)",
        "Financial Decision": r"(?:Financial Decision|Financial GO|财务可行性)",
        "Overall Decision": r"(?:Overall Decision|综合判断|综合决策)",
    }
    missing_decisions = [
        label
        for label, pattern in decision_patterns.items()
        if not re.search(pattern, text, flags=re.IGNORECASE)
    ]
    if missing_decisions:
        errors.append(
            "Decision layers are not explicit: " + ", ".join(missing_decisions)
        )
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "section_count": len(REQUIRED_SECTIONS) - len(missing_sections),
        "source_types_cited": source_hits,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint a product-selector report")
    parser.add_argument("report", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = lint(args.report.read_text(encoding="utf-8"))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
