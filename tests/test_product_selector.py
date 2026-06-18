from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "evals" / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import report_lint
import score_go_nogo
import build_review_bundle
import build_monitor_payload
import validate_config
import run_evals


class AttributeTaggerTests(unittest.TestCase):
    def run_tagger(self, dimensions: bool) -> tuple[dict, Path, tempfile.TemporaryDirectory]:
        temp = tempfile.TemporaryDirectory()
        output = Path(temp.name)
        command = [
            sys.executable,
            str(SCRIPTS / "attribute-tagger.py"),
            "--input",
            str(FIXTURES / "sample-electronics-category.json"),
            "--output-dir",
            str(output),
            "--price-unit",
            "cents",
            "--json-only",
        ]
        if dimensions:
            command.extend(
                [
                    "--dimensions-file",
                    str(ROOT / "references" / "dimensions" / "electronics.json"),
                ]
            )
        completed = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", check=False
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout), output, temp

    def test_confirmed_dimensions_and_blank_cells(self) -> None:
        result, output, temp = self.run_tagger(dimensions=True)
        self.addCleanup(temp.cleanup)
        self.assertFalse(result["requires_dimension_confirmation"])
        self.assertEqual(result["stats"]["products"], 8)
        self.assertEqual(result["stats"]["price"]["median"], 24.49)
        self.assertEqual(result["stats"]["fba_rate"], 0.75)
        statuses = [
            cell["supply_status"]
            for matrix in result["cross_analysis"].values()
            for cell in matrix["cells"]
        ]
        self.assertIn("blank_unvalidated", statuses)
        self.assertIn("high_demand_low_supply", statuses)
        scarce = [
            cell
            for matrix in result["cross_analysis"].values()
            for cell in matrix["cells"]
            if cell["supply_status"] == "scarce"
        ]
        self.assertTrue(scarce)
        self.assertTrue(all(cell["requires_demand_validation"] for cell in scarce))
        self.assertTrue(result["decision_eligible"])
        parsed = json.loads((output / "top100_parsed.json").read_text(encoding="utf-8"))
        lighting_item = next(item for item in parsed if item["asin"] == "TEST000007")
        self.assertNotEqual(lighting_item.get("connector"), "lightning")

    def test_unknown_category_creates_draft(self) -> None:
        result, output, temp = self.run_tagger(dimensions=False)
        self.addCleanup(temp.cleanup)
        self.assertTrue(result["requires_dimension_confirmation"])
        self.assertFalse(result["decision_eligible"])
        self.assertTrue(
            all(
                not matrix["decision_eligible"]
                for matrix in result["cross_analysis"].values()
            )
        )
        draft = json.loads((output / "dimension-draft.json").read_text(encoding="utf-8"))
        self.assertEqual(draft["status"], "draft")


class FinanceTests(unittest.TestCase):
    def run_finance(self, *arguments: str) -> dict:
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "finance.py"), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        return json.loads(completed.stdout)

    def test_reverse_finance_returns_sourcing_ceiling(self) -> None:
        result = self.run_finance(
            "reverse",
            "--price",
            "39.99",
            "--fba-fee",
            "8.2",
            "--commission-rate",
            "15",
            "--cpc",
            "0.8",
            "--cvr",
            "8",
            "--freight-assumption",
            "4",
        )
        self.assertEqual(result["mode"], "reverse")
        self.assertGreater(result["results"]["implied_product_cost_ceiling"], 0)
        self.assertIn("not a confirmed profit", result["interpretation"])

    def test_forward_finance_can_reject_bad_unit_economics(self) -> None:
        result = self.run_finance(
            "forward",
            "--price",
            "19.99",
            "--fba-fee",
            "7",
            "--commission-rate",
            "15",
            "--product-cost",
            "8",
            "--freight",
            "5",
            "--cpc",
            "1.2",
            "--cvr",
            "6",
        )
        self.assertEqual(result["financial_decision"], "NO-GO")

    def test_finance_rejects_invalid_rates(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "finance.py"),
                "reverse",
                "--price",
                "39.99",
                "--fba-fee",
                "8",
                "--commission-rate",
                "150",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("commission_rate", completed.stdout)

    def test_reverse_finance_omits_product_ceiling_without_freight(self) -> None:
        result = self.run_finance(
            "reverse",
            "--price",
            "39.99",
            "--fba-fee",
            "8.2",
            "--commission-rate",
            "15",
            "--cpc",
            "0.8",
            "--cvr",
            "8",
        )
        self.assertGreater(result["results"]["recommended_landed_cost_ceiling"], 0)
        self.assertIsNone(result["results"]["implied_product_cost_ceiling"])
        self.assertEqual(
            result["results"]["product_cost_ceiling_status"],
            "needs_freight_estimate",
        )


class BundledFinancialModelTests(unittest.TestCase):
    def run_reverse(self, freight: float | None) -> dict:
        inputs = {
            "price": 39.99,
            "fbaFee": 8.2,
            "commissionRate": 15,
            "storageFee": 0.1,
            "returnRate": 5,
            "adRatio": 60,
            "cpc": 0.8,
            "cvr": 8,
            "targetM": 2,
            "targetNetMargin": 15,
        }
        if freight is not None:
            inputs["freightAssumption"] = freight
        request = {
            "schema_version": "financial-model/v1",
            "operation": "reverse",
            "inputs": inputs,
        }
        completed = subprocess.run(
            ["node", str(SCRIPTS / "financial_model" / "cli.js")],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        return json.loads(completed.stdout)

    def test_total_landed_cost_is_primary_without_freight(self) -> None:
        result = self.run_reverse(None)["results"]["reverse"]
        self.assertGreater(result["recommendedLandedCostCeiling"], 0)
        self.assertIsNone(result["impliedProductCostCeiling"])
        self.assertEqual(result["costBasis"], "product_cost_plus_first_leg_freight")
        self.assertEqual(result["productCostCeilingStatus"], "needs_freight_estimate")

    def test_product_cost_ceiling_is_derived_after_freight(self) -> None:
        result = self.run_reverse(4)["results"]["reverse"]
        self.assertAlmostEqual(
            result["impliedProductCostCeiling"],
            max(0, result["recommendedLandedCostCeiling"] - 4),
            places=6,
        )
        self.assertEqual(result["productCostCeilingStatus"], "available")


class DecisionTests(unittest.TestCase):
    def test_finance_pending_caps_overall_decision(self) -> None:
        result = score_go_nogo.combine(
            {
                "scores": {
                    "market_size": 9,
                    "competition": 8,
                    "demand_clarity": 8,
                    "barrier": 8,
                },
                "hard_gates": {
                    "patent": "pass",
                    "compliance": "pass",
                    "product_safety": "pass",
                    "supply_chain": "pass",
                },
            }
        )
        self.assertEqual(result["market"]["decision"], "GO")
        self.assertEqual(result["finance"]["decision"], "PENDING")
        self.assertEqual(result["overall_decision"], "CONDITIONAL GO")

    def test_failed_hard_gate_forces_no_go(self) -> None:
        result = score_go_nogo.combine(
            {
                "scores": {
                    "market_size": 9,
                    "competition": 9,
                    "demand_clarity": 9,
                    "barrier": 9,
                    "profitability": 9,
                },
                "hard_gates": {"compliance": "fail"},
            }
        )
        self.assertEqual(result["overall_decision"], "NO-GO")

    def test_missing_hard_gates_are_pending(self) -> None:
        result = score_go_nogo.combine(
            {
                "scores": {
                    "market_size": 9,
                    "competition": 9,
                    "demand_clarity": 9,
                    "barrier": 9,
                    "profitability": 9,
                }
            }
        )
        self.assertEqual(result["overall_decision"], "CONDITIONAL GO")
        self.assertCountEqual(
            result["hard_gates"]["pending"],
            ["patent", "compliance", "product_safety", "supply_chain"],
        )

    def test_finance_result_can_be_merged_directly(self) -> None:
        result = score_go_nogo.combine(
            {
                "scores": {
                    "market_size": 9,
                    "competition": 9,
                    "demand_clarity": 9,
                    "barrier": 9,
                },
                "finance": {
                    "financial_decision": "GO",
                    "launch_feasibility": "GO",
                },
                "hard_gates": {
                    "patent": "pass",
                    "compliance": "pass",
                    "product_safety": "pass",
                    "supply_chain": "pass",
                },
            }
        )
        self.assertEqual(result["overall_decision"], "GO")


class WrapperAndReportTests(unittest.TestCase):
    def test_eval_manifest_is_valid_and_transparently_synthetic(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "run_evals.py"),
                "--manifest-only",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["fixture_counts"]["synthetic"], 5)
        self.assertEqual(result["fixture_counts"]["sorftime-live"], 0)
        self.assertFalse(result["live_gate"]["complete"])

    def test_eval_live_gate_fails_without_real_fixtures(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "run_evals.py"),
                "--manifest-only",
                "--require-live",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(completed.returncode, 1)
        result = json.loads(completed.stdout)
        self.assertFalse(result["valid"])
        self.assertIn("CategoryRequest", result["live_gate"]["missing_endpoints"])

    def test_eval_manifest_reports_bad_policy_without_crashing(self) -> None:
        payload = json.loads(
            (ROOT / "evals" / "evals.json").read_text(encoding="utf-8")
        )
        payload["live_fixture_policy"]["minimum_fixtures"] = "many"
        result = run_evals.validate_manifest(
            ROOT / "evals" / "evals.json", payload, require_live=False
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("integer" in error for error in result["errors"]))

    def test_sorftime_dry_run_does_not_require_cli(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "sorftime_call.py"),
                "CategoryRequest",
                '{"nodeId":"123"}',
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["estimated_cost"], 5)

    def test_sorftime_budget_gate_blocks_before_cli(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "sorftime_call.py"),
                "CategoryRequest",
                "--payload-file",
                str(FIXTURES / "category-request-payload.json"),
                "--remaining-budget",
                "4",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(completed.returncode, 3)
        self.assertIn("budget", completed.stdout.lower())

    def test_expected_report_passes_lint(self) -> None:
        text = (FIXTURES / "expected-report.md").read_text(encoding="utf-8")
        result = report_lint.lint(text)
        self.assertTrue(result["valid"], result)

    def test_report_with_placeholder_fails_lint(self) -> None:
        text = (FIXTURES / "expected-report.md").read_text(encoding="utf-8")
        result = report_lint.lint(text + "\n[X 待填]\n")
        self.assertFalse(result["valid"])

    def test_report_without_explicit_decision_layers_fails_lint(self) -> None:
        text = (FIXTURES / "expected-report.md").read_text(encoding="utf-8")
        text = text.replace("Market Decision", "市场判断")
        text = text.replace("Financial Decision", "财务判断")
        text = text.replace("Overall Decision", "最终意见")
        text = text.replace("市场可行性", "市场判断")
        text = text.replace("财务可行性", "财务判断")
        result = report_lint.lint(text)
        self.assertFalse(result["valid"])
        self.assertTrue(any("Decision layers" in error for error in result["errors"]))

    def test_review_bundle_has_stable_evidence_ids(self) -> None:
        first = build_review_bundle.normalize([FIXTURES / "sample-reviews.json"])
        second = build_review_bundle.normalize([FIXTURES / "sample-reviews.json"])
        self.assertEqual(first["counts"]["total"], 2)
        self.assertEqual(
            first["records"][0]["evidence_id"],
            second["records"][0]["evidence_id"],
        )
        self.assertEqual(first["counts"]["negative"], 1)

    def test_example_config_is_safe_dry_run(self) -> None:
        config = json.loads(
            (ROOT / "config.example.json").read_text(encoding="utf-8")
        )
        result = validate_config.validate(config)
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["write_mode"], "dry-run")

    def test_live_config_rejects_placeholder_tables(self) -> None:
        config = json.loads(
            (ROOT / "config.example.json").read_text(encoding="utf-8")
        )
        config["execution"]["write_mode"] = "live"
        result = validate_config.validate(config)
        self.assertFalse(result["valid"])

    def test_config_rejects_direct_secret_values(self) -> None:
        config = json.loads(
            (ROOT / "config.example.json").read_text(encoding="utf-8")
        )
        config["feishu"]["app_secret"] = "do-not-store-this"
        result = validate_config.validate(config)
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("direct secret" in error for error in result["errors"])
        )

    def test_config_reports_invalid_numeric_settings_without_crashing(self) -> None:
        config = json.loads(
            (ROOT / "config.example.json").read_text(encoding="utf-8")
        )
        config["execution"]["api_budget"] = "many"
        result = validate_config.validate(config)
        self.assertFalse(result["valid"])
        self.assertTrue(any("integer" in error for error in result["errors"]))

    def run_fake_sorftime(
        self, sequence: list[int], wrapper_encoding: str | None = None
    ) -> tuple[subprocess.CompletedProcess[str], int]:
        with tempfile.TemporaryDirectory() as temp:
            fake_dir = Path(temp)
            state = fake_dir / "count.txt"
            fake_script = fake_dir / "fake_sorftime.py"
            fake_script.write_text(
                "import json, os\n"
                "from pathlib import Path\n"
                "assert os.environ.get('PYTHONIOENCODING') == 'utf-8'\n"
                "assert os.environ.get('PYTHONUTF8') == '1'\n"
                "state = Path(os.environ['FAKE_SORFTIME_STATE'])\n"
                "count = int(state.read_text() or '0') if state.exists() else 0\n"
                "sequence = json.loads(os.environ['FAKE_SORFTIME_SEQUENCE'])\n"
                "code = sequence[min(count, len(sequence) - 1)]\n"
                "state.write_text(str(count + 1))\n"
                "print(json.dumps({'Code': code, 'Data': {'attempt': count + 1, "
                "'title': 'zero\\u200bwidth'}}, ensure_ascii=False))\n",
                encoding="utf-8",
            )
            fake_cmd = fake_dir / "sorftime.cmd"
            fake_cmd.write_text(
                f'@echo off\r\n"{sys.executable}" "%~dp0fake_sorftime.py" %*\r\n',
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["PATH"] = str(fake_dir) + os.pathsep + env.get("PATH", "")
            env["FAKE_SORFTIME_STATE"] = str(state)
            env["FAKE_SORFTIME_SEQUENCE"] = json.dumps(sequence)
            if wrapper_encoding:
                env["PYTHONIOENCODING"] = wrapper_encoding
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "sorftime_call.py"),
                    "CategoryRequest",
                    "--payload-file",
                    str(FIXTURES / "category-request-payload.json"),
                    "--attempts",
                    "3",
                    "--base-delay",
                    "0",
                    "--remaining-budget",
                    "10",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                check=False,
            )
            count = int(state.read_text()) if state.exists() else 0
            return completed, count

    def test_sorftime_code_99_retries_then_succeeds(self) -> None:
        completed, count = self.run_fake_sorftime([99, 0])
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(count, 2)
        result = json.loads(completed.stdout)
        self.assertEqual(result["_product_selector_meta"]["attempts"], 2)

    def test_sorftime_non_retryable_code_stops_immediately(self) -> None:
        completed, count = self.run_fake_sorftime([4, 0])
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(count, 1)

    def test_sorftime_utf8_output_bypasses_gbk_console_encoding(self) -> None:
        completed, count = self.run_fake_sorftime([0], wrapper_encoding="cp936")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(count, 1)
        result = json.loads(completed.stdout)
        self.assertEqual(
            result["response"]["Data"]["title"], "zero\u200bwidth"
        )

    def test_sorftime_live_call_requires_explicit_budget(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "sorftime_call.py"),
                "CategoryRequest",
                "--payload-file",
                str(FIXTURES / "category-request-payload.json"),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(completed.returncode, 3)
        self.assertIn("remaining-budget", completed.stdout)

    def test_sorftime_unknown_endpoint_cost_is_blocked(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "sorftime_call.py"),
                "FutureEndpoint",
                "{}",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(completed.returncode, 3)
        self.assertIn("unknown", completed.stdout.lower())

    def test_monitor_payload_uses_stable_upsert_key(self) -> None:
        payload = json.loads(
            (FIXTURES / "sample-product-request.json").read_text(encoding="utf-8")
        )
        result = build_monitor_payload.build(
            payload,
            "1:asin:test000001",
            1,
            "daily",
            "rec-test",
            "cents",
        )
        self.assertEqual(result["idempotency_key"], "1:asin:TEST000001")
        self.assertEqual(result["fields"]["初始售价"], 39.99)


class FixturePipelineTests(unittest.TestCase):
    def test_synthetic_pipeline_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            attributes_dir = run_dir / "attributes"
            attribute = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "attribute-tagger.py"),
                    "--input",
                    str(FIXTURES / "sample-electronics-category.json"),
                    "--dimensions-file",
                    str(ROOT / "references" / "dimensions" / "electronics.json"),
                    "--output-dir",
                    str(attributes_dir),
                    "--price-unit",
                    "cents",
                    "--json-only",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(attribute.returncode, 0, attribute.stderr)

            finance = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "finance.py"),
                    "reverse",
                    "--price",
                    "39.99",
                    "--fba-fee",
                    "8.20",
                    "--commission-rate",
                    "15",
                    "--cpc",
                    "0.80",
                    "--cvr",
                    "8",
                    "--freight-assumption",
                    "4",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(finance.returncode, 0, finance.stderr)
            reverse = json.loads(finance.stdout)
            self.assertEqual(reverse["mode"], "reverse")

            decision = score_go_nogo.combine(
                {
                    "scores": {
                        "market_size": 8,
                        "competition": 7,
                        "demand_clarity": 8,
                        "barrier": 7,
                    },
                    "hard_gates": {
                        "patent": "pending",
                        "compliance": "pass",
                        "supply_chain": "pending",
                    },
                }
            )
            self.assertEqual(decision["overall_decision"], "CONDITIONAL GO")

            review_bundle = build_review_bundle.normalize(
                [FIXTURES / "sample-reviews.json"]
            )
            self.assertEqual(review_bundle["counts"]["total"], 2)

            product_payload = json.loads(
                (FIXTURES / "sample-product-request.json").read_text(
                    encoding="utf-8"
                )
            )
            monitoring = build_monitor_payload.build(
                product_payload,
                "1:asin:test000001",
                1,
                "daily",
                "",
                "cents",
            )
            self.assertEqual(monitoring["operation"], "upsert")

            report = report_lint.lint(
                (FIXTURES / "expected-report.md").read_text(encoding="utf-8")
            )
            self.assertTrue(report["valid"], report)
            self.assertTrue((attributes_dir / "attribute_summary.json").exists())
            self.assertTrue((attributes_dir / "cross_analysis.json").exists())


if __name__ == "__main__":
    unittest.main()
