#!/usr/bin/env python3
"""Validate product-selector configuration and live-write safety."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def is_placeholder(value: Any) -> bool:
    text = str(value or "").strip()
    return not text or text.startswith("<") or text.lower() in {"todo", "tbd"}


def exposed_secrets(payload: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            normalized_key = str(key).lower().replace("-", "_")
            sensitive = normalized_key in {
                "app_secret",
                "appsecret",
                "access_token",
                "tenant_access_token",
                "base_token",
            }
            if sensitive and not normalized_key.endswith("_env") and not is_placeholder(value):
                findings.append(path)
            findings.extend(exposed_secrets(value, path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(exposed_secrets(value, f"{prefix}[{index}]"))
    return findings


def integer_setting(
    payload: dict[str, Any], name: str, errors: list[str]
) -> int | None:
    try:
        return int(payload.get(name))
    except (TypeError, ValueError):
        errors.append(f"{name} must be an integer")
        return None


def valid_env_name(value: Any) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(value or "")))


def validate(config: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if config.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    secret_paths = exposed_secrets(config)
    if secret_paths:
        errors.append(
            "Configuration contains direct secret/token values: "
            + ", ".join(secret_paths)
        )

    execution = config.get("execution", {})
    if not isinstance(execution, dict):
        return {
            "valid": False,
            "write_mode": "dry-run",
            "errors": ["execution must be an object"],
            "warnings": warnings,
        }
    write_mode = execution.get("write_mode", "dry-run")
    if write_mode not in {"dry-run", "live"}:
        errors.append("execution.write_mode must be dry-run or live")
    analysis_mode = execution.get("analysis_mode", "full")
    if analysis_mode not in {"quick", "full", "deep-voc", "batch"}:
        errors.append("execution.analysis_mode is unsupported")
    api_budget = integer_setting(execution, "api_budget", errors)
    if api_budget is not None and api_budget <= 0:
        errors.append("execution.api_budget must be positive")
    max_parallel = integer_setting(execution, "max_parallel", errors)
    if max_parallel is not None and max_parallel not in range(1, 9):
        errors.append("execution.max_parallel must be between 1 and 8")
    if is_placeholder(execution.get("output_dir")):
        errors.append("execution.output_dir is required")

    finance = config.get("finance", {})
    if not isinstance(finance, dict):
        finance = {}
        errors.append("finance must be an object")
    if finance.get("engine", "bundled-js") != "bundled-js":
        errors.append("finance.engine must be bundled-js")
    if finance.get("scenario_profile", "moderate") not in {
        "conservative",
        "moderate",
        "aggressive",
    }:
        errors.append("finance.scenario_profile is unsupported")
    if finance.get("feishu_percent_scale", "fraction") not in {"fraction", "whole"}:
        errors.append("finance.feishu_percent_scale must be fraction or whole")
    try:
        target_m = float(finance.get("target_m"))
        if target_m <= 0:
            errors.append("finance.target_m must be positive")
    except (TypeError, ValueError):
        errors.append("finance.target_m must be numeric")
    for name in (
        "target_net_margin",
        "default_return_rate",
        "default_ad_order_share",
        "fallback_ad_rate",
    ):
        try:
            value = float(finance.get(name))
            if not 0 <= value <= 1:
                errors.append(f"finance.{name} must be between 0 and 1")
        except (TypeError, ValueError):
            errors.append(f"finance.{name} must be numeric")
    available_capital = finance.get("available_capital")
    if available_capital is None:
        warnings.append("finance.available_capital is unset; Launch Feasibility will remain PENDING.")
    else:
        try:
            if float(available_capital) <= 0:
                errors.append("finance.available_capital must be positive when set")
        except (TypeError, ValueError):
            errors.append("finance.available_capital must be numeric or null")
    max_payback = integer_setting(finance, "max_payback_months", errors)
    if max_payback is not None and max_payback not in range(1, 25):
        errors.append("finance.max_payback_months must be between 1 and 24")
    salvage_rate = finance.get("inventory_salvage_rate")
    if salvage_rate is not None:
        try:
            if not 0 <= float(salvage_rate) <= 1:
                errors.append("finance.inventory_salvage_rate must be between 0 and 1")
        except (TypeError, ValueError):
            errors.append("finance.inventory_salvage_rate must be numeric or null")

    feishu = config.get("feishu", {})
    if not isinstance(feishu, dict):
        feishu = {}
        errors.append("feishu must be an object")
    adapter = feishu.get("adapter", "auto")
    if adapter not in {"auto", "builtin-feishu", "mcp", "provider", "lark-cli"}:
        errors.append("feishu.adapter is unsupported")
    tables = feishu.get("tables", {})
    if not isinstance(tables, dict):
        tables = {}
        errors.append("feishu.tables must be an object")
    if write_mode == "live":
        if is_placeholder(feishu.get("base_token_env")):
            errors.append("live mode requires feishu.base_token_env")
        elif not valid_env_name(feishu.get("base_token_env")):
            errors.append("feishu.base_token_env must be an environment variable name")
        missing_tables = [name for name, value in tables.items() if is_placeholder(value)]
        if missing_tables:
            errors.append(
                "live mode has placeholder Feishu tables: " + ", ".join(missing_tables)
            )
    elif any(not is_placeholder(value) for value in tables.values()):
        warnings.append("Feishu table ids are configured, but write_mode remains dry-run.")

    integrations = config.get("integrations", {})
    if not isinstance(integrations, dict):
        integrations = {}
        errors.append("integrations must be an object")
    monitoring = integrations.get("monitoring", {})
    if not isinstance(monitoring, dict):
        monitoring = {}
        errors.append("integrations.monitoring must be an object")
    if monitoring.get("enabled") and is_placeholder(monitoring.get("table_id_env")):
        errors.append("monitoring.enabled requires integrations.monitoring.table_id_env")
    elif monitoring.get("enabled") and not valid_env_name(
        monitoring.get("table_id_env")
    ):
        errors.append("monitoring.table_id_env must be an environment variable name")
    monitoring_write_mode = monitoring.get("write_mode", "dry-run")
    if monitoring_write_mode not in {"dry-run", "live"}:
        errors.append("monitoring.write_mode must be dry-run or live")
    if monitoring_write_mode == "live" and write_mode != "live":
        errors.append("monitoring live mode requires execution.write_mode=live")

    cross_market = integrations.get("cross_market_scan", {})
    if not isinstance(cross_market, dict):
        cross_market = {}
        errors.append("integrations.cross_market_scan must be an object")
    if cross_market.get("enabled"):
        domains = cross_market.get("domains")
        if not isinstance(domains, list) or not domains:
            errors.append("cross_market_scan.enabled requires at least one domain")
        elif any(not isinstance(domain, int) or not 1 <= domain <= 12 for domain in domains):
            errors.append("cross_market_scan.domains must contain domain ids 1-12")
        cross_budget = integer_setting(cross_market, "api_budget", errors)
        if cross_budget is not None and cross_budget <= 0:
            errors.append("cross_market_scan.api_budget must be positive")

    return {
        "valid": not errors,
        "write_mode": write_mode,
        "errors": errors,
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate product-selector config")
    parser.add_argument("config", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = validate(json.loads(args.config.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
