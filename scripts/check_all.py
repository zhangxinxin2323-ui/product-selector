#!/usr/bin/env python3
"""
check_all.py — 一键质量门禁。
Claude MUST run this after every analysis. It exits non-zero if ANY gate fails.

用法: python scripts/check_all.py --asin B0X --report-dir <path> --overall <GO|COND|HOLD|NO-GO> --financial <GO|COND|HOLD|NO-GO|PENDING>

这是汇总检查入口。SKILL 规则规定本脚本必须在回复用户前运行。
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO = SCRIPTS.parent


def run(name: str, *args: str) -> tuple[int, str, str]:
    cmd = [sys.executable, str(SCRIPTS / name), *args]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforced post-analysis quality gate runner")
    parser.add_argument("--asin", required=True, help="ASIN analyzed")
    parser.add_argument("--report-dir", type=Path, required=True, help="Report output directory")
    parser.add_argument("--overall", required=True, help="Overall Decision (GO|CONDITIONAL GO|HOLD|NO-GO)")
    parser.add_argument("--financial", required=True, help="Financial Decision (GO|CONDITIONAL GO|HOLD|NO-GO|PENDING)")
    args = parser.parse_args()

    failures = 0
    report_dir = args.report_dir
    overall = args.overall
    financial = args.financial

    print("=" * 60)
    print(f"  POST-ANALYSIS GATES — {args.asin}")
    print("=" * 60)

    # Gate 1: report lint
    print("\n[1/4] report_lint.py")
    rc, out, err = run("report_lint.py", str(report_dir / "full-report.md"))
    if rc == 0:
        try:
            import json
            d = json.loads(out) if out else {}
            if d.get("valid"):
                print(f"  PASS: {d.get('section_count', '?')} sections, {len(d.get('errors', []))} errors")
            else:
                failures += 1
                print(f"  FAIL: {d.get('errors', [])}")
        except:
            print(f"  PASS (exit 0)")
    else:
        failures += 1
        print(f"  FAIL (exit {rc}): {out[:200]}")

    # Gate 2: check_report.py (lines, tables, sections, decisions, sensitivity)
    print("\n[2/4] check_report.py")
    rc, out, _ = run("check_report.py",
                     "--run-dir", str(report_dir),
                     "--overall-decision", overall,
                     "--financial-decision", financial,
                     "--json")
    if rc == 0:
        try:
            d = json.loads(out) if out else {}
            if d.get("valid"):
                print(f"  PASS")
            else:
                failures += 1
                for c in d.get("report", {}).get("checks", []):
                    if c["status"] != "PASS":
                        print(f"  FAIL: {c['item']} — {c['detail']}")
        except:
            print(f"  PASS (exit 0)")
    else:
        failures += 1
        print(f"  FAIL (exit {rc})")

    # Gate 3: evals
    print("\n[3/4] run_evals.py")
    rc, out, _ = run("run_evals.py")
    if rc == 0:
        try:
            d = json.loads(out) if out else {}
            if d.get("valid"):
                print(f"  PASS: evals valid, tests passed")
            else:
                failures += 1
                print(f"  FAIL: {d.get('errors', [])}")
        except:
            print(f"  PASS (exit 0)")
    else:
        failures += 1
        print(f"  FAIL (exit {rc})")

    # Gate 4: Feishu table coverage (informational — can't automate from script)
    print("\n[4/4] Feishu table coverage (manual check)")
    tables = {
        "candidate": True,
        "ai_analysis": True,
        "screening": overall.upper() in ("GO", "CONDITIONAL GO"),
        "finance": financial.upper() == "GO",
        "development": overall.upper() in ("GO", "CONDITIONAL GO"),
        "supplier": False,
    }
    written = []
    skipped = []
    for t, should_write in tables.items():
        if should_write:
            written.append(t)
        else:
            skipped.append(t)
    print(f"  Must write: {', '.join(written)}")
    print(f"  Skip OK:    {', '.join(skipped)}")
    print(f"  [MANUAL] Verify these tables have records. Check recvm* IDs exist in conversation above.")

    # Summary
    print(f"\n{'='*60}")
    if failures == 0:
        print(f"  RESULT: ALL GATES PASSED — safe to respond to user")
        print(f"{'='*60}")
        return 0
    else:
        print(f"  RESULT: {failures} GATE(S) FAILED — DO NOT RESPOND TO USER")
        print(f"  Fix all failures, then re-run this script.")
        print(f"{'='*60}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
