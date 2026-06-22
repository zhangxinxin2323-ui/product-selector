#!/usr/bin/env python3
"""Replay the committed product-selector golden sample without live API calls."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "evals" / "fixtures"


def run(command: list[str]) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.returncode, "\n".join(
        item for item in (completed.stdout, completed.stderr) if item
    ).strip()


def nested(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for key in path.split("."):
        value = value[key]
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    commands = [
        [
            sys.executable,
            str(ROOT / "scripts" / "build_pivot_table.py"),
            "--input",
            str(FIXTURES / "sample-electronics-category.json"),
            "--dimensions-file",
            str(ROOT / "references" / "dimensions" / "electronics.json"),
            "--tagged-json",
            str(FIXTURES / "sample-electronics-tagged.json"),
            "--price-unit",
            "cents",
            "--output",
            str(args.output_dir / "pivot.csv"),
        ],
        [
            sys.executable,
            str(ROOT / "scripts" / "report_lint.py"),
            str(FIXTURES / "expected-report.md"),
        ],
    ]
    failures: list[str] = []
    command_results = []
    for command in commands:
        returncode, output = run(command)
        command_results.append(
            {"command": Path(command[1]).name, "returncode": returncode}
        )
        if returncode:
            failures.append(f"{Path(command[1]).name}: {output[-500:]}")

    node = shutil.which("node")
    if not node:
        failures.append("node executable not found")
    else:
        returncode, output = run(
            [
                node,
                str(ROOT / "scripts" / "financial_model" / "cli.js"),
                "--input",
                str(FIXTURES / "sample-financial-model-request.json"),
                "--output",
                str(args.output_dir / "financial-result.json"),
            ]
        )
        command_results.append(
            {"command": "financial_model/cli.js", "returncode": returncode}
        )
        if returncode:
            failures.append(f"financial_model/cli.js: {output[-500:]}")

    actual: dict[str, Any] = {"schema_version": 1}
    pivot_path = args.output_dir / "pivot.csv"
    finance_path = args.output_dir / "financial-result.json"
    if pivot_path.is_file():
        with pivot_path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        actual["pivot"] = {
            "rows": len(rows),
            "first_asin": rows[0]["ASIN"] if rows else None,
            "first_price": float(rows[0]["售价($)"]) if rows else None,
        }
    if finance_path.is_file():
        finance = json.loads(finance_path.read_text(encoding="utf-8"))
        actual["finance"] = {
            "financial_decision": nested(finance, "assessment.financial_decision"),
            "launch_feasibility": nested(finance, "assessment.launch_feasibility"),
            "base_payback_month": nested(
                finance, "results.scenarios.base.summary.paybackMonth"
            ),
            "pessimistic_payback_month": nested(
                finance, "results.scenarios.pessimistic.summary.paybackMonth"
            ),
            "unit_profit": nested(finance, "results.static.metrics.unitProfit"),
        }

    expected = json.loads(
        (FIXTURES / "sample-run-expected.json").read_text(encoding="utf-8")
    )
    if actual != expected:
        failures.append(f"golden summary mismatch: expected={expected}, actual={actual}")

    result = {
        "schema_version": 1,
        "valid": not failures,
        "commands": command_results,
        "expected": expected,
        "actual": actual,
        "errors": failures,
    }
    (args.output_dir / "sample-run-summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
