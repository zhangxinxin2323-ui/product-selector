#!/usr/bin/env python3
"""Deterministic forward and reverse unit economics for product selection."""

from __future__ import annotations

import argparse
import json
from typing import Any


def rate(value: float) -> float:
    return value / 100.0 if value > 1 else value


def money(value: float) -> float:
    return round(value, 2)


def ratio(value: float) -> float:
    return round(value, 4)


def validate_percentage(name: str, value: float, *, positive: bool = False) -> None:
    normalized = rate(value)
    lower_ok = normalized > 0 if positive else normalized >= 0
    if not lower_ok or normalized > 1:
        qualifier = "greater than 0 and " if positive else ""
        raise ValueError(
            f"{name} must be {qualifier}at most 1.0 (or 100 when using percent units)."
        )


def validate_inputs(args: argparse.Namespace) -> None:
    if args.price <= 0:
        raise ValueError("price must be positive.")
    for name in ("fba_fee", "storage_fee"):
        if getattr(args, name) < 0:
            raise ValueError(f"{name} cannot be negative.")
    validate_percentage("commission_rate", args.commission_rate)
    validate_percentage("return_rate", args.return_rate)
    validate_percentage("ad_order_share", args.ad_order_share)
    validate_percentage("fallback_ad_rate", args.fallback_ad_rate)
    if args.cpc is not None and args.cpc < 0:
        raise ValueError("cpc cannot be negative.")
    if args.cvr is not None:
        validate_percentage("cvr", args.cvr, positive=True)

    if args.mode == "reverse":
        if args.target_m <= 0:
            raise ValueError("target_m must be positive.")
        validate_percentage("target_margin", args.target_margin)
        if args.freight_assumption is not None and args.freight_assumption < 0:
            raise ValueError("freight_assumption cannot be negative.")
    else:
        for name in ("landed_cost", "product_cost"):
            value = getattr(args, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative.")
        if args.freight < 0:
            raise ValueError("freight cannot be negative.")


def advertising_cost(
    price: float,
    cpc: float | None,
    cvr: float | None,
    ad_order_share: float,
    fallback_ad_rate: float,
) -> tuple[float, list[str], str]:
    assumptions: list[str] = []
    if cpc is not None and cvr is not None and rate(cvr) > 0:
        cost = cpc / rate(cvr) * rate(ad_order_share)
        return cost, assumptions, "actual_cpc_cvr"
    assumptions.append(
        f"Advertising cost estimated at {rate(fallback_ad_rate):.1%} of price."
    )
    return price * rate(fallback_ad_rate), assumptions, "estimated_ad_rate"


def base_payout(
    price: float,
    fba_fee: float,
    commission_rate: float,
    storage_fee: float,
    return_rate: float,
    ad_cost: float,
) -> dict[str, float]:
    commission = price * rate(commission_rate)
    return_allowance = price * rate(return_rate)
    payout = price - fba_fee - commission - storage_fee - return_allowance - ad_cost
    return {
        "commission": commission,
        "return_allowance": return_allowance,
        "ad_cost": ad_cost,
        "payout_before_landed_cost": payout,
    }


def reverse_analysis(args: argparse.Namespace) -> dict[str, Any]:
    ad_cost, assumptions, ad_source = advertising_cost(
        args.price,
        args.cpc,
        args.cvr,
        args.ad_order_share,
        args.fallback_ad_rate,
    )
    payout = base_payout(
        args.price,
        args.fba_fee,
        args.commission_rate,
        args.storage_fee,
        args.return_rate,
        ad_cost,
    )
    available = max(0.0, payout["payout_before_landed_cost"])
    target_by_m = available / args.target_m if args.target_m > 0 else 0.0
    target_by_margin = max(0.0, available - args.price * rate(args.target_margin))
    recommended_landed = min(target_by_m, target_by_margin)
    max_product_cost = (
        None
        if args.freight_assumption is None
        else max(0.0, recommended_landed - args.freight_assumption)
    )
    if args.freight_assumption is None:
        assumptions.append(
            "Product cost ceiling omitted because per-unit first-leg freight was not provided."
        )

    confidence = "high" if ad_source == "actual_cpc_cvr" else "medium"
    return {
        "schema_version": 1,
        "mode": "reverse",
        "confidence": confidence,
        "inputs": {
            "price": money(args.price),
            "fba_fee": money(args.fba_fee),
            "commission_rate": ratio(rate(args.commission_rate)),
            "storage_fee": money(args.storage_fee),
            "return_rate": ratio(rate(args.return_rate)),
            "target_m": args.target_m,
            "target_margin": ratio(rate(args.target_margin)),
            "freight_assumption": (
                money(args.freight_assumption)
                if args.freight_assumption is not None
                else None
            ),
            "advertising_source": ad_source,
        },
        "results": {
            "break_even_landed_cost": money(available),
            "target_landed_cost_for_m": money(target_by_m),
            "target_landed_cost_for_margin": money(target_by_margin),
            "recommended_landed_cost_ceiling": money(recommended_landed),
            "implied_product_cost_ceiling": (
                money(max_product_cost) if max_product_cost is not None else None
            ),
            "cost_basis": "product_cost_plus_first_leg_freight",
            "product_cost_ceiling_status": (
                "needs_freight_estimate"
                if args.freight_assumption is None
                else "available"
            ),
        },
        "components": {key: money(value) for key, value in payout.items()},
        "assumptions": assumptions,
        "interpretation": (
            "This is a sourcing ceiling, not a confirmed profit result. "
            "Replace assumptions with supplier, freight, CPC and click-CVR data."
        ),
    }


def financial_decision(m_value: float, net_margin: float, net_profit: float) -> str:
    if net_profit <= 0 or m_value < 1.3:
        return "NO-GO"
    if m_value >= 2.0 and net_margin >= 0.15:
        return "GO"
    if m_value >= 1.6 and net_margin >= 0.10:
        return "CONDITIONAL GO"
    return "HOLD"


def forward_analysis(args: argparse.Namespace) -> dict[str, Any]:
    landed_cost = (
        args.landed_cost
        if args.landed_cost is not None
        else (args.product_cost or 0.0) + args.freight
    )
    if landed_cost <= 0:
        raise ValueError("Provide --landed-cost or a positive --product-cost.")

    ad_cost, assumptions, ad_source = advertising_cost(
        args.price,
        args.cpc,
        args.cvr,
        args.ad_order_share,
        args.fallback_ad_rate,
    )
    payout = base_payout(
        args.price,
        args.fba_fee,
        args.commission_rate,
        args.storage_fee,
        args.return_rate,
        ad_cost,
    )
    payout_before_cost = payout["payout_before_landed_cost"]
    net_profit = payout_before_cost - landed_cost
    net_margin = net_profit / args.price if args.price else 0.0
    m_value = payout_before_cost / landed_cost if landed_cost else 0.0
    ad_space = (
        args.price
        - landed_cost
        - args.fba_fee
        - payout["commission"]
        - args.storage_fee
        - payout["return_allowance"]
    ) / args.price
    break_even_cpc = None
    if args.cvr is not None and rate(args.cvr) > 0 and rate(args.ad_order_share) > 0:
        max_ad_cost = max(
            0.0,
            args.price
            - landed_cost
            - args.fba_fee
            - payout["commission"]
            - args.storage_fee
            - payout["return_allowance"],
        )
        break_even_cpc = max_ad_cost * rate(args.cvr) / rate(args.ad_order_share)

    return {
        "schema_version": 1,
        "mode": "forward",
        "confidence": "high" if ad_source == "actual_cpc_cvr" else "medium",
        "financial_decision": financial_decision(m_value, net_margin, net_profit),
        "inputs": {
            "price": money(args.price),
            "landed_cost": money(landed_cost),
            "fba_fee": money(args.fba_fee),
            "commission_rate": ratio(rate(args.commission_rate)),
            "storage_fee": money(args.storage_fee),
            "return_rate": ratio(rate(args.return_rate)),
            "advertising_source": ad_source,
        },
        "results": {
            "payout_before_landed_cost": money(payout_before_cost),
            "net_profit_per_unit": money(net_profit),
            "net_margin": ratio(net_margin),
            "m_value": round(m_value, 3),
            "advertising_space": ratio(ad_space),
            "break_even_cpc": money(break_even_cpc)
            if break_even_cpc is not None
            else None,
        },
        "components": {key: money(value) for key, value in payout.items()},
        "assumptions": assumptions,
    }


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--price", type=float, required=True)
    parser.add_argument("--fba-fee", type=float, required=True)
    parser.add_argument("--commission-rate", type=float, required=True)
    parser.add_argument("--storage-fee", type=float, default=0.0)
    parser.add_argument("--return-rate", type=float, required=True,
                       help="Category-specific: Clothing/Shoes=0.15, Electronics=0.05, Home/Furniture=0.08, Pet=0.08, Sports=0.07, Tools=0.05, Office=0.05, Other=0.05")
    parser.add_argument("--cpc", type=float)
    parser.add_argument("--cvr", type=float)
    parser.add_argument("--ad-order-share", type=float, default=0.60)
    parser.add_argument("--fallback-ad-rate", type=float, default=0.15)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Product-selector finance engine")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    reverse = subparsers.add_parser("reverse")
    add_common(reverse)
    reverse.add_argument("--target-m", type=float, default=2.0)
    reverse.add_argument("--target-margin", type=float, default=0.15)
    reverse.add_argument("--freight-assumption", type=float)

    forward = subparsers.add_parser("forward")
    add_common(forward)
    forward.add_argument("--landed-cost", type=float)
    forward.add_argument("--product-cost", type=float)
    forward.add_argument("--freight", type=float, default=0.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        validate_inputs(args)
        result = reverse_analysis(args) if args.mode == "reverse" else forward_analysis(args)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
