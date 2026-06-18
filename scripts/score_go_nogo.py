#!/usr/bin/env python3
"""Combine market, finance and hard-gate decisions deterministically."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


MARKET_WEIGHTS = {
    "market_size": 0.25,
    "competition": 0.3125,
    "demand_clarity": 0.1875,
    "barrier": 0.25,
}

REQUIRED_GATES = ("patent", "compliance", "product_safety", "supply_chain")
VALID_FINANCIAL_DECISIONS = {"GO", "CONDITIONAL GO", "HOLD", "NO-GO", "PENDING"}
VALID_LAUNCH_DECISIONS = {
    "GO",
    "CONDITIONAL GO",
    "HOLD",
    "NO-GO",
    "PENDING",
    "NOT_RUN",
}


def score_decision(score: float) -> str:
    if score >= 7.5:
        return "GO"
    if score >= 6.0:
        return "CONDITIONAL GO"
    if score >= 4.0:
        return "HOLD"
    return "NO-GO"


def validate_score(name: str, value: Any) -> float:
    number = float(value)
    if not 0 <= number <= 10:
        raise ValueError(f"{name} must be between 0 and 10")
    return number


def combine(payload: dict[str, Any]) -> dict[str, Any]:
    scores = payload.get("scores", payload)
    market_values = {
        name: validate_score(name, scores[name]) for name in MARKET_WEIGHTS
    }
    market_score = sum(
        market_values[name] * weight for name, weight in MARKET_WEIGHTS.items()
    )
    market_decision = score_decision(market_score)

    profitability = scores.get("profitability")
    financial_score = (
        validate_score("profitability", profitability)
        if profitability is not None
        else None
    )
    finance_payload = payload.get("finance", {})
    financial_override = payload.get("financial_decision")
    if financial_override is None and isinstance(finance_payload, dict):
        financial_override = finance_payload.get("financial_decision")
    if financial_override is not None:
        financial_decision = str(financial_override).strip().upper()
        if financial_decision not in VALID_FINANCIAL_DECISIONS:
            raise ValueError(f"Unsupported financial decision: {financial_decision}")
    else:
        financial_decision = (
            score_decision(financial_score)
            if financial_score is not None
            else "PENDING"
        )

    launch_override = payload.get("launch_feasibility")
    if launch_override is None and isinstance(finance_payload, dict):
        launch_override = finance_payload.get("launch_feasibility")
    launch_decision = (
        str(launch_override).strip().upper()
        if launch_override is not None
        else "PENDING"
    )
    if launch_decision not in VALID_LAUNCH_DECISIONS:
        raise ValueError(f"Unsupported launch feasibility: {launch_decision}")

    gates = payload.get("hard_gates", {})
    normalized_gates = {
        name: str(value).strip().lower() for name, value in gates.items()
    }
    for name in REQUIRED_GATES:
        normalized_gates.setdefault(name, "pending")
    failed = [name for name, value in normalized_gates.items() if value == "fail"]
    pending = [
        name
        for name, value in normalized_gates.items()
        if value not in {"pass", "fail", "not_applicable"}
    ]

    if failed:
        overall = "NO-GO"
        reason = f"Hard gate failed: {', '.join(failed)}"
    elif market_decision == "NO-GO":
        overall = "NO-GO"
        reason = "Market viability is below the entry threshold."
    elif market_decision == "HOLD":
        overall = "HOLD"
        reason = "Market evidence is not strong enough to advance."
    elif financial_decision == "NO-GO":
        overall = "NO-GO"
        reason = "Unit economics fail even though market evidence may be positive."
    elif financial_decision == "HOLD":
        overall = "HOLD"
        reason = "Financial viability is below the advancement threshold."
    elif launch_decision == "NO-GO":
        overall = "NO-GO"
        reason = "Launch feasibility failed under the configured constraints."
    elif launch_decision == "HOLD":
        overall = "HOLD"
        reason = "Launch capital or payback constraints require a pause."
    elif financial_decision == "PENDING" or launch_decision in {"PENDING", "NOT_RUN"} or pending:
        overall = "CONDITIONAL GO"
        reason = "Market can advance to validation, but finance, launch, or hard gates are pending."
    elif market_decision == "GO" and financial_decision == "GO" and launch_decision == "GO":
        overall = "GO"
        reason = "Market, finance, launch feasibility and hard gates all pass."
    else:
        overall = "CONDITIONAL GO"
        reason = "At least one decision layer is conditional."

    return {
        "schema_version": 1,
        "market": {
            "score": round(market_score, 2),
            "decision": market_decision,
            "weights": MARKET_WEIGHTS,
            "dimension_scores": market_values,
        },
        "finance": {
            "score": round(financial_score, 2)
            if financial_score is not None
            else None,
            "decision": financial_decision,
            "launch_feasibility": launch_decision,
        },
        "hard_gates": {
            "statuses": normalized_gates,
            "failed": failed,
            "pending": pending,
        },
        "overall_decision": overall,
        "reason": reason,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Market and finance decision combiner")
    parser.add_argument("--input", type=Path, help="JSON input; defaults to stdin")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw = args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read()
    try:
        result = combine(json.loads(raw))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
