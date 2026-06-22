#!/usr/bin/env python3
"""Validate eval provenance and run the deterministic product-selector suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "evals" / "evals.json"
VALID_PROVENANCE = {"synthetic", "sorftime-live"}
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        raw = handle.read()
    # Normalize line endings to LF for cross-platform consistency
    normalized = raw.replace(b"\r\n", b"\n")
    digest.update(normalized)
    return digest.hexdigest()


def resolved_fixture(manifest: Path, relative_path: str) -> Path:
    path = (manifest.parent / relative_path).resolve()
    try:
        path.relative_to(manifest.parent.resolve())
    except ValueError as exc:
        raise ValueError(f"Fixture escapes eval directory: {relative_path}") from exc
    return path


def validate_manifest(
    manifest: Path, payload: dict[str, Any], require_live: bool
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != 3:
        errors.append("eval schema_version must be 3")

    catalog = payload.get("fixture_catalog")
    if not isinstance(catalog, list) or not catalog:
        errors.append("fixture_catalog must be a non-empty list")
        catalog = []

    known_paths: set[str] = set()
    live_endpoints: set[str] = set()
    counts = {"synthetic": 0, "sorftime-live": 0}
    for index, fixture in enumerate(catalog):
        if not isinstance(fixture, dict):
            errors.append(f"fixture_catalog[{index}] must be an object")
            continue
        relative_path = str(fixture.get("path") or "")
        provenance = str(fixture.get("provenance") or "")
        if not relative_path or relative_path in known_paths:
            errors.append(f"fixture_catalog[{index}] has a missing or duplicate path")
            continue
        known_paths.add(relative_path)
        if provenance not in VALID_PROVENANCE:
            errors.append(f"{relative_path} has unsupported provenance: {provenance}")
            continue
        counts[provenance] += 1
        try:
            path = resolved_fixture(manifest, relative_path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not path.is_file():
            errors.append(f"Fixture does not exist: {relative_path}")
            continue
        expected_hash = str(fixture.get("sha256") or "").lower()
        if not SHA256_PATTERN.fullmatch(expected_hash):
            errors.append(f"Fixture has invalid SHA-256 metadata: {relative_path}")
        actual_hash = file_hash(path)
        if expected_hash != actual_hash:
            errors.append(f"Fixture hash mismatch: {relative_path}")

        if provenance == "sorftime-live":
            missing = [
                field
                for field in ("endpoint", "captured_at", "domain", "redacted")
                if field not in fixture
            ]
            if missing:
                errors.append(
                    f"Live fixture {relative_path} lacks metadata: {', '.join(missing)}"
                )
            endpoint = str(fixture.get("endpoint") or "")
            if endpoint:
                live_endpoints.add(endpoint)
            domain = fixture.get("domain")
            if not isinstance(domain, int) or not 1 <= domain <= 12:
                errors.append(f"Live fixture {relative_path} has an invalid domain")
            if fixture.get("redacted") is not True:
                errors.append(f"Live fixture {relative_path} must set redacted=true")
            try:
                datetime.fromisoformat(
                    str(fixture.get("captured_at") or "").replace("Z", "+00:00")
                )
            except ValueError:
                errors.append(
                    f"Live fixture {relative_path} has an invalid captured_at timestamp"
                )

    evals = payload.get("evals")
    if not isinstance(evals, list) or not evals:
        errors.append("evals must be a non-empty list")
        evals = []
    eval_ids: set[str] = set()
    for index, case in enumerate(evals):
        if not isinstance(case, dict):
            errors.append(f"evals[{index}] must be an object")
            continue
        case_id = str(case.get("id") or "")
        if not case_id or case_id in eval_ids:
            errors.append(f"evals[{index}] has a missing or duplicate id")
        eval_ids.add(case_id)
        files = case.get("files", [])
        if not isinstance(files, list):
            errors.append(f"Eval {case_id or index} files must be a list")
            files = []
        for relative_path in files:
            if relative_path not in known_paths:
                errors.append(
                    f"Eval {case_id or index} references uncatalogued fixture: "
                    f"{relative_path}"
                )

    policy = payload.get("live_fixture_policy", {})
    try:
        minimum_live = int(policy.get("minimum_fixtures", 0) or 0)
    except (TypeError, ValueError):
        errors.append("live_fixture_policy.minimum_fixtures must be an integer")
        minimum_live = 0
    endpoint_policy = policy.get("required_endpoints", [])
    if not isinstance(endpoint_policy, list):
        errors.append("live_fixture_policy.required_endpoints must be a list")
        endpoint_policy = []
    required_endpoints = set(endpoint_policy)
    missing_endpoints = sorted(required_endpoints - live_endpoints)
    live_complete = (
        counts["sorftime-live"] >= minimum_live and not missing_endpoints
    )
    if not live_complete:
        message = (
            "Live fixture gate is pending: "
            f"{counts['sorftime-live']}/{minimum_live} fixtures; "
            f"missing endpoints={missing_endpoints}"
        )
        if require_live:
            errors.append(message)
        else:
            warnings.append(message)

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "fixture_counts": counts,
        "live_gate": {
            "required": require_live,
            "complete": live_complete,
            "minimum_fixtures": minimum_live,
            "required_endpoints": sorted(required_endpoints),
            "observed_endpoints": sorted(live_endpoints),
            "missing_endpoints": missing_endpoints,
        },
        "eval_count": len(evals),
    }


def run_tests() -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    combined = "\n".join((completed.stdout, completed.stderr))
    match = re.search(r"Ran\s+(\d+)\s+tests?", combined)
    return {
        "passed": completed.returncode == 0,
        "test_count": int(match.group(1)) if match else None,
        "returncode": completed.returncode,
        "summary": [line for line in combined.splitlines() if line.strip()][-4:],
    }


def run_sample_replay() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "replay_sample_run.py"),
                "--output-dir",
                temp,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {}
        return {
            "passed": completed.returncode == 0 and payload.get("valid") is True,
            "returncode": completed.returncode,
            "errors": payload.get("errors", [completed.stderr[-500:]]),
            "actual": payload.get("actual"),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run product-selector eval gates")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument("--require-live", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2))
        return 2

    result = validate_manifest(args.manifest, payload, args.require_live)
    if not args.manifest_only:
        result["tests"] = run_tests()
        if not result["tests"]["passed"]:
            result["valid"] = False
            result["errors"].append("Deterministic test suite failed.")
        result["sample_replay"] = run_sample_replay()
        if not result["sample_replay"]["passed"]:
            result["valid"] = False
            result["errors"].append("Golden sample replay failed.")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
