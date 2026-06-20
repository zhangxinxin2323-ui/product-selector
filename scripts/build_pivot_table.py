#!/usr/bin/env python3
"""
build_pivot_table.py — Attribute tagging + pivot-ready CSV generation.
Splits the work: script handles data extraction & validation, Claude handles LLM tagging.

Usage:
  python scripts/build_pivot_table.py --input top100.json --output pivot.csv [--prompt-only]

Step 1: Extract 100 ASINs + base fields from CategoryRequest JSON
Step 2: Output a prompt file for Claude to perform attribute discovery + tagging
Step 3: Read Claude's tagged JSON, validate 100/100 coverage
Step 4: Output CSV with all fields
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

# Base fields always extracted from CategoryRequest
BASE_FIELDS = [
    ("ASIN", "asin", "str"),
    ("品牌", "brand", "str"),
    ("标题", "title", "str"),
    ("售价($)", "price", "float"),
    ("月销量", "sales", "int"),
    ("评论数", "reviews", "int"),
    ("评分", "rating", "float"),
    ("上架天数", "days", "int"),
    ("FBA", "is_fba", "bool"),
]

MAX_TITLES_PER_PROMPT = 100


def extract_products(input_path: Path) -> list[dict]:
    """Extract product data from CategoryRequest JSON (handles CLI prefix)."""
    raw = input_path.read_text(encoding="utf-8", errors="replace")
    start = raw.find("{")
    if start == -1:
        raise ValueError("No JSON found in input file")
    data = json.loads(raw[start:])
    products = data.get("Data", {}).get("Products", [])
    if not products:
        raise ValueError("No Products found in JSON")

    result = []
    for p in products:
        t = (p.get("Title") or "").strip()
        if not t:
            continue
        pr = p.get("Price") or 0
        if isinstance(pr, (int, float)) and pr > 100:
            pr = pr / 100  # cents → dollars
        row = {
            "asin": (p.get("Asin") or "").strip(),
            "brand": (p.get("Brand") or "").strip(),
            "title": t,
            "price": round(pr, 2),
            "sales": p.get("SalesVolumeOfMonth") or 0,
            "reviews": p.get("RatingsCount") or 0,
            "rating": p.get("Ratings") or 0,
            "days": p.get("OnlineDays") or 0,
            "is_fba": bool(p.get("IsFBA")),
        }
        result.append(row)
    return result


def generate_prompt(products: list[dict], output_path: Path, step: str = "discover", dimensions: list | None = None) -> Path:
    """Generate a prompt file for LLM attribute discovery OR tagging.

    step='discover': Claude outputs dimension definitions only (5-8 dims)
    step='tag': Claude tags all products using confirmed dimensions
    """
    prompt_path = output_path.with_suffix(
        ".dimensions.prompt.txt" if step == "discover" else ".tagging.prompt.txt"
    )
    lines = []

    if step == "discover":
        lines.append("# Step 1: Discover Purchase-Decision Attribute Dimensions\n")
        lines.append(f"Read {len(products)} product titles below.\n")
        lines.append("Extract 5-8 dimensions consumers use to compare these products.\n")
        lines.append("For each dimension output: name, label(中文), description(1句), 3-6 example values.\n")
        lines.append("Focus on dimensions that differentiate products — not generic descriptors.\n")
        lines.append("\nDO NOT tag individual products yet. Only output dimension definitions.\n")
    else:
        lines.append("# Step 2: Tag All Products with Confirmed Dimensions\n")
        lines.append("Using the confirmed dimensions below, tag every product.\n")
        lines.append("For each ASIN, fill in all dimension values from the title.\n")
        lines.append("Use 'unknown' when the title doesn't reveal a dimension.\n")
        if dimensions:
            lines.append("\n## Confirmed Dimensions (DO NOT modify)\n")
            for d in dimensions:
                lines.append(f"  - {d.get('name','?')} ({d.get('label','?')}): {d.get('description','?')}")
                lines.append(f"    Allowed values: {', '.join(d.get('examples',[]))}\n")
        lines.append(f"\nTotal products to tag: {len(products)}\n")

    lines.append(f"\n## Product Titles (first {MAX_TITLES_PER_PROMPT})\n")
    for i, p in enumerate(products[:MAX_TITLES_PER_PROMPT]):
        lines.append(f"{i+1:3d}. [{p['brand']}] ${p['price']:.0f} | {p['title'][:120]}")
    lines.append(f"\n## Output Format\n")
    lines.append("```json")
    if step == "discover":
        lines.append('{')
        lines.append('  "dimensions": [')
        lines.append('    {"name": "...", "label": "...", "description": "...", "examples": ["..."]}')
        lines.append('  ]')
        lines.append('}')
    else:
        lines.append('{')
        lines.append('  "products": [')
        lines.append('    {"asin": "B0X", "dim1_value": "...", "dim2_value": "..."}')
        lines.append('  ]')
        lines.append('}')
    lines.append("```")
    lines.append("\nOnly output the JSON. No other text.")

    prompt_path.write_text("\n".join(lines), encoding="utf-8")
    return prompt_path


def validate_tagging(products: list[dict], tagged: list[dict]) -> dict:
    """Validate that all 100 ASINs are tagged."""
    result = {"total": len(products), "tagged": len(tagged), "missing": [], "unknown_counts": {}}
    tagged_asins = {t["asin"] for t in tagged}
    for p in products:
        if p["asin"] not in tagged_asins:
            result["missing"].append(p["asin"])

    # Count unknown values per dimension
    if tagged:
        dims = [k for k in tagged[0] if k != "asin"]
        for d in dims:
            unknown = sum(1 for t in tagged if t.get(d, "") in ("", "unknown", "other"))
            result["unknown_counts"][d] = unknown

    return result


def merge_and_write_csv(products: list[dict], tagged: list[dict], output_path: Path) -> None:
    """Merge base fields + tagged attributes → pivot-ready CSV."""
    tagged_map = {t["asin"]: t for t in tagged}

    # Discover attribute columns from tagged data
    attr_cols = []
    if tagged:
        attr_cols = [k for k in tagged[0] if k != "asin"]

def generate_enrich_list(products: list[dict], tagged: list[dict], unknown_threshold: int = 2) -> Path | None:
    """Find ASINs with too many unknown attributes that need ProductRequest enrichment."""
    tagged_map = {t["asin"]: t for t in tagged}
    attr_cols = [k for k in tagged[0] if k != "asin"] if tagged else []

    needs_enrichment = []
    for p in products:
        tag = tagged_map.get(p["asin"], {})
        unknown_count = sum(1 for ac in attr_cols if tag.get(ac, "") in ("", "unknown", "other"))
        if unknown_count >= unknown_threshold:
            needs_enrichment.append({
                "asin": p["asin"],
                "title": p["title"],
                "unknown_attrs": unknown_count,
                "total_attrs": len(attr_cols),
            })

    if needs_enrichment:
        output_path = Path("enrich_asins.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(needs_enrichment, f, indent=2, ensure_ascii=False)
        print(f"⚠️  {len(needs_enrichment)} ASINs need ProductRequest enrichment → {output_path}")
        print(f"   Run: ProductRequest for each ASIN, extract Description/bullets, re-tag unknown attrs")
        return output_path
    return None
    base_names = [b[1] for b in BASE_FIELDS[:1]] + [b[0] for b in BASE_FIELDS[1:]]
    # Use Chinese labels for base fields
    base_labels = [b[0] for b in BASE_FIELDS]
    all_cols = base_labels + attr_cols

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(all_cols)

        for p in products:
            row = [p.get(b[1], "") for b in BASE_FIELDS]
            tag = tagged_map.get(p["asin"], {})
            for ac in attr_cols:
                row.append(tag.get(ac, "unknown"))
            writer.writerow(row)

    print(f"CSV written: {output_path} ({len(products)} rows, {len(all_cols)} columns)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build pivot-ready CSV from Top100 + LLM tagging")
    parser.add_argument("--input", type=Path, required=True, help="CategoryRequest JSON")
    parser.add_argument("--output", type=Path, required=True, help="Output CSV path")
    parser.add_argument("--step", choices=("discover", "tag"), default="discover",
                       help="discover: output dimension definitions | tag: tag products with confirmed dims")
    parser.add_argument("--tagged-json", type=Path, help="Claude's tagged JSON (if already run)")
    parser.add_argument("--dimensions-json", type=Path, help="Confirmed dimensions JSON (for tag step)")
    parser.add_argument("--prompt-only", action="store_true", help="Only generate prompt file, don't build CSV")
    args = parser.parse_args()

    products = extract_products(args.input)
    print(f"Extracted {len(products)} products from {args.input}")

    if args.prompt_only:
        dims = None
        if args.step == "tag" and args.dimensions_json:
            dims_data = json.loads(args.dimensions_json.read_text(encoding="utf-8"))
            dims = dims_data if isinstance(dims_data, list) else dims_data.get("dimensions", [])
        prompt_path = generate_prompt(products, args.output, step=args.step, dimensions=dims)
        print(f"Prompt written: {prompt_path}")
        print(f"\nNext: Claude reads this, outputs JSON.")
        if args.step == "discover":
            print(f"  Then: User confirms dimensions → re-run: --step tag --dimensions-json <dims.json> --prompt-only")
        else:
            print(f"  Then: re-run: --tagged-json <claude_output.json> to build CSV")
        return 0

    if args.tagged_json:
        tagged = json.loads(args.tagged_json.read_text(encoding="utf-8"))
        if isinstance(tagged, dict):
            tagged = tagged.get("products", tagged.get("data", []))

        validation = validate_tagging(products, tagged)
        print(f"Tagged: {validation['tagged']}/{validation['total']}")
        if validation["missing"]:
            print(f"Missing ASINs: {validation['missing'][:5]}...")
        for dim, count in validation["unknown_counts"].items():
            pct = count / max(validation["total"], 1) * 100
            print(f"  {dim}: {count} unknown ({pct:.0f}%)")

        # Phase 2 check: find ASINs needing ProductRequest enrichment
        enrich_file = generate_enrich_list(products, tagged)
        if enrich_file:
            print("→ Next: run ProductRequest for enrichment ASINs, then re-tag with descriptions")
            print("  sorftime api ProductRequest '{\"asin\":\"<asin1>,<asin2>,...,<asin10>\"}' --domain 1")
            print("  Max 10 ASINs per call. Prioritize ASINs with most unknown attrs.")

        merge_and_write_csv(products, tagged, args.output)
        return 0

    # No tagged JSON yet → generate prompt
    prompt_path = generate_prompt(products, args.output)
    print(f"No tagged JSON provided. Prompt generated: {prompt_path}")
    print("Claude should read this file, perform attribute discovery + tagging,")
    print(f"save the JSON output, then re-run: python {__file__} --input {args.input} --output {args.output} --tagged-json <json>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
