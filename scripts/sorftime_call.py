#!/usr/bin/env python3
"""Cross-platform Sorftime CLI wrapper with bounded retries and dry-run."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ENDPOINT_COSTS = {
    "ProductRequest": 1,
    "ASINRequestKeywordv2": 1,
    "KeywordRequest": 1,
    "KeywordExtends": 5,
    "CategoryRequest": 5,
    "CategoryTrend": 5,
    "KeywordSearchResults": 5,
    "ASINKeywordRanking": 2,
    "ProductReviewsQuery": 5,
    "ProductReviewsCollectionStatusQuery": 0,
}

LOCAL_FATAL_ERRORS = (
    "codec can't encode",
    "unicodeencodeerror",
    "invalid request",
    "authentication",
    "not authenticated",
)


def extract_json(text: str) -> Any:
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
            return value
        except json.JSONDecodeError:
            continue
    raise ValueError("Sorftime output did not contain valid JSON")


def response_code(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("Code", "code"):
            if key in payload:
                return str(payload[key])
    return None


def find_executable() -> str:
    executable = shutil.which("sorftime.cmd") or shutil.which("sorftime")
    if not executable:
        raise FileNotFoundError("sorftime executable was not found on PATH")
    return executable


def emit(payload: Any, output_path: Path | None = None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    data = (text + "\n").encode("utf-8")
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
    else:
        sys.stdout.write(text.encode("ascii", "backslashreplace").decode("ascii") + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reliable Sorftime API invocation")
    parser.add_argument("endpoint")
    parser.add_argument("payload", nargs="?", help="JSON request payload")
    parser.add_argument(
        "--payload-file",
        type=Path,
        help="Read request JSON from a file; preferred on Windows PowerShell",
    )
    parser.add_argument("--domain", type=int, default=1)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--base-delay", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--remaining-budget", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--allow-unbudgeted",
        action="store_true",
        help="Explicitly allow a live call without --remaining-budget",
    )
    parser.add_argument(
        "--allow-unknown-cost",
        action="store_true",
        help="Explicitly allow an endpoint absent from the local cost map",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.payload_file:
        raw_payload = args.payload_file.read_text(encoding="utf-8")
    elif args.payload and args.payload.startswith("@"):
        raw_payload = Path(args.payload[1:]).read_text(encoding="utf-8")
    elif args.payload:
        raw_payload = args.payload
    else:
        emit({"error": "Provide a JSON payload or --payload-file."})
        return 2
    try:
        request_payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"Invalid request JSON: {exc}"}))
        return 2
    if not isinstance(request_payload, dict):
        emit({"error": "Sorftime request payload must be a JSON object."})
        return 2
    if not 1 <= args.domain <= 12:
        emit({"error": "domain must be between 1 and 12."})
        return 2
    if args.attempts < 1 or args.base_delay < 0 or args.timeout <= 0:
        emit(
            {
                "error": (
                    "attempts must be positive, base-delay cannot be negative, "
                    "and timeout must be positive."
                )
            }
        )
        return 2
    if args.remaining_budget is not None and args.remaining_budget < 0:
        emit({"error": "remaining-budget cannot be negative."})
        return 2

    cost = ENDPOINT_COSTS.get(args.endpoint)
    if cost is None and not args.allow_unknown_cost:
        emit(
            {
                "error": "Endpoint cost is unknown; explicit approval is required.",
                "endpoint": args.endpoint,
            }
        )
        return 3
    if (
        not args.dry_run
        and args.remaining_budget is None
        and not args.allow_unbudgeted
    ):
        emit(
            {
                "error": "Live calls require --remaining-budget.",
                "endpoint": args.endpoint,
                "estimated_cost": cost,
            }
        )
        return 3
    if args.remaining_budget is not None:
        if cost is not None and cost > args.remaining_budget:
            emit(
                {
                    "error": "API budget would be exceeded.",
                    "endpoint": args.endpoint,
                    "estimated_cost": cost,
                    "remaining_budget": args.remaining_budget,
                }
            )
            return 3
    if args.dry_run:
        emit(
            {
                "dry_run": True,
                "endpoint": args.endpoint,
                "payload": request_payload,
                "domain": args.domain,
                "estimated_cost": cost,
                "remaining_budget_after": (
                    args.remaining_budget - cost
                    if args.remaining_budget is not None and cost is not None
                    else None
                ),
            }
        )
        return 0

    try:
        executable = find_executable()
    except FileNotFoundError as exc:
        print(json.dumps({"error": str(exc)}))
        return 127

    last_error = ""
    started_at = time.monotonic()
    child_env = os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONUTF8"] = "1"
    for attempt in range(1, max(1, args.attempts) + 1):
        command = [
            executable,
            "api",
            args.endpoint,
            json.dumps(request_payload, ensure_ascii=False, separators=(",", ":")),
            "--domain",
            str(args.domain),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=args.timeout,
                check=False,
                env=child_env,
            )
            combined = "\n".join(
                part for part in (completed.stdout, completed.stderr) if part
            )
            lowered_output = combined.lower()
            if completed.returncode != 0 and any(
                marker in lowered_output for marker in LOCAL_FATAL_ERRORS
            ):
                emit(
                    {
                        "error": "Sorftime failed with a non-retryable local error",
                        "detail": combined.strip(),
                        "endpoint": args.endpoint,
                        "domain": args.domain,
                        "attempts": attempt,
                        "estimated_cost": cost,
                        "retryable": False,
                        "elapsed_seconds": round(
                            time.monotonic() - started_at, 3
                        ),
                    },
                    args.output,
                )
                return 1
            payload = extract_json(combined)
            code = response_code(payload)
            if code == "99" and attempt < args.attempts:
                time.sleep(args.base_delay * (2 ** (attempt - 1)))
                continue
            if code in {"4", "97"}:
                normalized = {
                    "response": payload,
                    "_product_selector_meta": {
                        "endpoint": args.endpoint,
                        "domain": args.domain,
                        "attempts": attempt,
                        "estimated_cost": cost,
                        "remaining_budget_after": (
                            args.remaining_budget - cost
                            if args.remaining_budget is not None and cost is not None
                            else None
                        ),
                        "elapsed_seconds": round(time.monotonic() - started_at, 3),
                        "retryable": False,
                    },
                }
                emit(normalized, args.output)
                return 1
            if completed.returncode == 0 and code != "99":
                normalized = {
                    "response": payload,
                    "_product_selector_meta": {
                        "endpoint": args.endpoint,
                        "domain": args.domain,
                        "attempts": attempt,
                        "estimated_cost": cost,
                        "remaining_budget_after": (
                            args.remaining_budget - cost
                            if args.remaining_budget is not None and cost is not None
                            else None
                        ),
                        "elapsed_seconds": round(time.monotonic() - started_at, 3),
                        "retryable": False,
                    },
                }
                emit(normalized, args.output)
                return 0
            last_error = f"exit={completed.returncode}, code={code}"
        except UnicodeEncodeError as exc:
            emit(
                {
                    "error": "Sorftime response could not be written to stdout",
                    "detail": str(exc),
                    "attempts": attempt,
                    "retryable": False,
                },
                args.output,
            )
            return 1
        except (subprocess.TimeoutExpired, ValueError) as exc:
            last_error = str(exc)
        if attempt < args.attempts:
            time.sleep(args.base_delay * (2 ** (attempt - 1)))

    emit(
        {
            "error": "Sorftime request failed after bounded retries",
            "detail": last_error,
            "attempts": args.attempts,
            "endpoint": args.endpoint,
            "domain": args.domain,
            "estimated_cost": cost,
            "elapsed_seconds": round(time.monotonic() - started_at, 3),
        }
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
