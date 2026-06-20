#!/usr/bin/env python3
"""Map bundled financial-model results to a dry-run Feishu finance upsert."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def scaled_percent(value: Any, scale: str) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number / 100 if scale == "fraction" else number


def input_confidence(provenance: dict[str, Any]) -> str:
    statuses = {
        str(value.get("status", "")).lower()
        for value in provenance.values()
        if isinstance(value, dict)
    }
    if not statuses:
        return "low"
    if "estimated" in statuses or "hypothesis" in statuses:
        return "medium"
    if statuses.issubset({"measured", "user_provided"}):
        return "high"
    return "low"


def compact_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return {
        name: value
        for name, value in fields.items()
        if value is not None and value != ""
    }


def build(
    model: dict[str, Any],
    analysis_key: str,
    domain: int,
    *,
    percent_scale: str = "fraction",
    evidence_index: str = "",
    linked_candidate_id: str = "",
    linked_screening_id: str = "",
    linked_development_id: str = "",
    calculated_at: str | None = None,
) -> dict[str, Any]:
    if model.get("status") != "ok":
        raise ValueError("financial model result must have status=ok")
    if percent_scale not in {"fraction", "whole"}:
        raise ValueError("percent_scale must be fraction or whole")

    inputs = model.get("inputs", {})
    results = model.get("results", {})
    assessment = model.get("assessment", {})
    static = results.get("static", {})
    static_metrics = static.get("metrics", {})
    reverse = results.get("reverse", {})
    scenarios = results.get("scenarios", {})
    base_summary = scenarios.get("base", {}).get("summary", {})
    pessimistic_summary = scenarios.get("pessimistic", {}).get("summary", {})
    provenance = model.get("provenance", {})
    timestamp = calculated_at or datetime.now(timezone.utc).isoformat()

    fields: dict[str, Any] = {
        "分析键": analysis_key,
        "数据站点": domain,
        "最近分析日期": timestamp,
        "模型版本": model.get("model_version"),
        "决策策略版本": model.get("decision_policy_version"),
        "输入哈希": model.get("input_hash"),
        "计算模式": model.get("operation"),
        "售价": inputs.get("price"),
        "产品成本": inputs.get("productCost"),
        "头程运费": (
            inputs.get("shippingCost")
            if inputs.get("shippingCost") is not None
            else inputs.get("freightAssumption")
        ),
        "落地成本": static_metrics.get("landedCost"),
        "FBA费": inputs.get("fbaFee"),
        "佣金率": scaled_percent(inputs.get("commissionRate"), percent_scale),
        "仓储费": inputs.get("storageFee"),
        "退货率": scaled_percent(inputs.get("returnRate"), percent_scale),
        "当前CPC": inputs.get("cpc"),
        "当前点击CVR": scaled_percent(inputs.get("cvr"), percent_scale),
        "广告订单占比": scaled_percent(inputs.get("adRatio"), percent_scale),
        "净利润": static_metrics.get("unitProfit"),
        "净利率": scaled_percent(static_metrics.get("netMarginPct"), percent_scale),
        "M值": static_metrics.get("M"),
        "广告空间": scaled_percent(static_metrics.get("adHeadroomPct"), percent_scale),
        "盈亏平衡CPC": static_metrics.get("breakEvenCPC"),
        "盈亏平衡CVR": scaled_percent(static_metrics.get("breakEvenCVR"), percent_scale),
        "Financial Decision": assessment.get("financial_decision"),
        "Launch Feasibility": assessment.get("launch_feasibility"),
        "最大可承受落地成本": reverse.get("breakEvenLandedCost"),
        "目标落地成本上限": reverse.get("recommendedLandedCostCeiling"),
        "隐含采购价上限": reverse.get("impliedProductCostCeiling"),
        "首批数量": base_summary.get("firstBatchQty"),
        "首批投入": base_summary.get("firstBatchCost"),
        "峰值资金需求": base_summary.get("peakCashRequirement"),
        "最大损失估算": base_summary.get("maximumLossAtSalvage"),
        "回本月份": base_summary.get("paybackMonth"),
        "首次月利润转正月份": base_summary.get("monthlyProfitPositiveMonth"),
        "12月总广告费": base_summary.get("totalAdSpend"),
        "12月累计利润": base_summary.get("totalProfit"),
        "期末现金流": base_summary.get("cumulativeCashFlowFinal"),
        "悲观情景峰值资金": pessimistic_summary.get("peakCashRequirement"),
        "悲观情景回本月份": pessimistic_summary.get("paybackMonth"),
        "财务置信度": input_confidence(provenance),
        "假设与置信度": json.dumps(
            {
                "assumptions": model.get("assumptions", []),
                "warnings": model.get("warnings", []),
                "provenance": provenance,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "证据索引": evidence_index,
        "关联初选": linked_candidate_id,
        "关联初筛": linked_screening_id,
        "关联开发": linked_development_id,
    }
    fields = compact_fields(fields)
    required = ["分析键", "模型版本", "输入哈希", "Financial Decision"]
    missing = [name for name in required if name not in fields]
    return {
        "schema_version": 1,
        "write_mode": "dry-run",
        "operation": "upsert",
        "logical_table": "finance",
        "idempotency_key": f"{analysis_key}:finance",
        "percent_scale": percent_scale,
        "fields": fields,
        "missing_fields": missing,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Feishu finance upsert payload")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--analysis-key", required=True)
    parser.add_argument("--domain", type=int, default=1)
    parser.add_argument("--percent-scale", choices=("fraction",), default="fraction",
                       help="Only 0-1 fraction is supported. whole mode removed per SKILL rule 9.")
    parser.add_argument("--evidence-index", default="")
    parser.add_argument("--linked-candidate-id", default="")
    parser.add_argument("--linked-screening-id", default="")
    parser.add_argument("--linked-development-id", default="")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = build(
            json.loads(args.input.read_text(encoding="utf-8")),
            args.analysis_key,
            args.domain,
            percent_scale=args.percent_scale,
            evidence_index=args.evidence_index,
            linked_candidate_id=args.linked_candidate_id,
            linked_screening_id=args.linked_screening_id,
            linked_development_id=args.linked_development_id,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0 if not result["missing_fields"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
