#!/usr/bin/env python3
"""
check_report.py — 报告质量门禁。每次分析后运行。
检查: 报告完整性、飞书表覆盖、证据保存。

用法: python scripts/check_report.py --run-dir <report-dir>

Returns exit code 0 only when ALL gates pass.
Claude MUST fix all failures before responding to the user.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


# ── Gate definitions ────────────────────────────────────────

REQUIRED_REPORT_SECTIONS = [
    "Executive Summary",
    "市场概况",
    "竞争格局",
    "属性分布",
    "交叉分析",
    "VOC",
    "供需缺口",
    "财务分析",
    "进入壁垒",
    "Go/No-Go",
    "产品矩阵",
    "数据来源",
]

MIN_REPORT_LINES = 250
MIN_TABLE_LINES = 120

# Tables that SHOULD exist based on Overall Decision
FEISHU_BASE_TOKEN = "LgO2bmmgnabbylsaJtTc4gt9n2c"
TABLES = {
    "candidate": "tbljJBWDxaLerJsN",
    "ai_analysis": "tblMeN1P5LvXsp2e",
    "screening": "tblPhc8dHOelKPPF",
    "finance": "tblllu3JJYrG5KGE",
    "development": "tbl3dtXNC3Emy38k",
    "supplier": "tblu1Q70vnmsiBZ5",
}


# ── Check functions ──────────────────────────────────────────

def check_report(report_dir: Path) -> dict:
    """Check full-report.md and decision-card.html exist and pass lint."""
    result = {"passed": True, "checks": []}

    report_md = report_dir / "full-report.md"
    decision_card = report_dir / "decision-card.html"

    if not report_md.exists():
        result["passed"] = False
        result["checks"].append({"status": "FAIL", "item": "full-report.md", "detail": "File not found"})
        return result
    if not decision_card.exists():
        result["passed"] = False
        result["checks"].append({"status": "FAIL", "item": "decision-card.html", "detail": "File not found"})

    content = report_md.read_text(encoding="utf-8")
    lines = content.split("\n")
    line_count = len(lines)
    table_lines = sum(1 for line in lines if "|" in line)

    found_sections = []
    for section in REQUIRED_REPORT_SECTIONS:
        if section in content:
            found_sections.append(section)
    missing = [s for s in REQUIRED_REPORT_SECTIONS if s not in content]

    checks = []

    if line_count >= MIN_REPORT_LINES:
        checks.append({"status": "PASS", "item": f"report_lines", "detail": f"{line_count}/{MIN_REPORT_LINES}"})
    else:
        result["passed"] = False
        checks.append({"status": "FAIL", "item": f"report_lines", "detail": f"{line_count}/{MIN_REPORT_LINES} — too short, missing detail"})

    if table_lines >= MIN_TABLE_LINES:
        checks.append({"status": "PASS", "item": f"table_lines", "detail": f"{table_lines}/{MIN_TABLE_LINES}"})
    else:
        result["passed"] = False
        checks.append({"status": "FAIL", "item": f"table_lines", "detail": f"{table_lines}/{MIN_TABLE_LINES} — skeleton report, no substance"})

    if not missing:
        checks.append({"status": "PASS", "item": "sections", "detail": f"{len(found_sections)}/{len(REQUIRED_REPORT_SECTIONS)} present"})
    else:
        result["passed"] = False
        checks.append({"status": "FAIL", "item": "sections", "detail": f"Missing: {', '.join(missing)}"})

    # Source citation check
    source_tokens = ("ProductRequest", "KeywordRequest", "CategoryRequest", "CategoryTrend")
    cited = [t for t in source_tokens if t in content]
    if len(cited) >= 3:
        checks.append({"status": "PASS", "item": "source_citations", "detail": f"{len(cited)}/{len(source_tokens)}"})
    else:
        result["passed"] = False
        checks.append({"status": "FAIL", "item": "source_citations", "detail": f"Only {len(cited)}/{len(source_tokens)} — missing evidence"})

    # Decision layer check
    has_market = "Market Decision" in content
    has_financial = "Financial Decision" in content
    has_overall = "Overall Decision" in content
    if has_market and has_financial and has_overall:
        checks.append({"status": "PASS", "item": "decision_layers", "detail": "Market/Financial/Overall all present"})
    else:
        missing_dec = []
        if not has_market: missing_dec.append("Market")
        if not has_financial: missing_dec.append("Financial")
        if not has_overall: missing_dec.append("Overall")
        result["passed"] = False
        checks.append({"status": "FAIL", "item": "decision_layers", "detail": f"Missing: {', '.join(missing_dec)}"})

    # Sensitivity table check
    has_sensitivity = "广告占比敏感性" in content or "Ad Ratio Sensitivity" in content
    if has_sensitivity:
        checks.append({"status": "PASS", "item": "ad_sensitivity_table", "detail": "Present"})
    else:
        result["passed"] = False
        checks.append({"status": "FAIL", "item": "ad_sensitivity_table", "detail": "Missing — required by Rule 13"})

    if decision_card.exists():
        checks.append({"status": "PASS", "item": "decision-card.html", "detail": "Present"})
    else:
        result["passed"] = False
        checks.append({"status": "FAIL", "item": "decision-card.html", "detail": "Missing"})

    result["checks"].extend(checks)
    return result


def check_feishu(overall_decision: str, financial_decision: str) -> dict:
    """Verify expected Feishu tables are written. Returns what SHOULD be checked.
    Note: This cannot actually verify Feishu writes from a script without MCP access.
    It outputs the EXPECTED table coverage for Claude to verify."""

    tables_expected = {
        "candidate": True,
        "ai_analysis": True,
        "screening": overall_decision.upper() in ("GO", "CONDITIONAL GO"),
        "finance": financial_decision.upper() == "GO",
        "development": overall_decision.upper() in ("GO", "CONDITIONAL GO"),
        "supplier": False,  # Always manual
    }

    checks = []
    for table_name, expected in tables_expected.items():
        status = "MUST_WRITE" if expected else "SKIP_OK"
        checks.append({
            "table": table_name,
            "expected": status,
            "detail": "Table must be written and read-back verified" if expected else "Correct to skip"
        })

    return {"tables_expected": tables_expected, "checks": checks}


def check_evidence(run_dir: Path) -> dict:
    """Check raw data files and evidence index exist."""
    result = {"passed": True, "checks": []}

    raw_dir = run_dir / "raw"
    if raw_dir.exists() and list(raw_dir.iterdir()):
        result["checks"].append({"status": "PASS", "item": "raw_data", "detail": f"raw/ directory exists with files"})
    else:
        # Accept that raw data may be in /tmp/ — just note it
        result["checks"].append({"status": "WARN", "item": "raw_data", "detail": "raw/ not found in run-dir — check /tmp/ for CLI outputs"})

    # Check evals pass this session
    return result


# ── Main ─────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Post-analysis quality gate validator")
    parser.add_argument("--run-dir", type=Path, required=True, help="Report output directory")
    parser.add_argument("--overall-decision", type=str, default="PENDING",
                        help="Overall Decision from analysis (GO|CONDITIONAL GO|HOLD|NO-GO)")
    parser.add_argument("--financial-decision", type=str, default="PENDING",
                        help="Financial Decision from analysis (GO|CONDITIONAL GO|HOLD|NO-GO|PENDING)")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    report_result = check_report(args.run_dir)
    feishu_result = check_feishu(args.overall_decision, args.financial_decision)
    evidence_result = check_evidence(args.run_dir)

    all_passed = (
        report_result["passed"] and
        evidence_result["passed"]
    )

    if args.json:
        output = {
            "valid": all_passed,
            "report": report_result,
            "feishu_expected": feishu_result,
            "evidence": evidence_result,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("  POST-ANALYSIS QUALITY GATE")
        print("=" * 60)

        print("\n  REPORT:")
        for c in report_result["checks"]:
            icon = "[PASS]" if c["status"] == "PASS" else ("[WARN]" if c["status"] == "WARN" else "[FAIL]")
            print(f"    {icon} {c['item']}: {c['detail']}")

        print("\n  FEISHU (expected coverage):")
        for c in feishu_result["checks"]:
            icon = "[WRITE]" if c["expected"] == "MUST_WRITE" else "[SKIP]"
            print(f"    {icon} {c['table']}: {c['expected']}")

        print(f"\n  EVIDENCE:")
        for c in evidence_result["checks"]:
            icon = "[PASS]" if c["status"] == "PASS" else "[WARN]"
            print(f"    {icon} {c['item']}: {c['detail']}")

        print(f"\n  {'='*60}")
        if all_passed:
            print(f"  RESULT: ALL GATES PASSED")
        else:
            print(f"  RESULT: GATES FAILED — fix before responding to user")
            failed = [c["item"] for c in report_result["checks"] if c["status"] == "FAIL"]
            if failed:
                print(f"  Failed items: {', '.join(failed)}")
        print(f"  {'='*60}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
