#!/usr/bin/env python3
"""Regression tests for discover-workload-model artifact behavior."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "plugins/system-design/skills/discover-workload-model"
SCRIPT = SKILL_ROOT / "scripts/workload.py"
FIXTURES = ROOT / "tests/fixtures/discover-workload-model"


class WorkloadContractTest(unittest.TestCase):
    def call(self, script: Path, *arguments: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(script), *[str(argument) for argument in arguments]],
            text=True,
            capture_output=True,
            check=False,
        )

    def load(self, name: str) -> dict:
        value = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        if value.get("schema_version") == 2:
            for item in value["open_questions"]:
                item.update(state="open", resolution=None, reason="未決として一覧確認した")
            value["question_review"] = {
                "question_ids": [item["id"] for item in value["open_questions"]],
                "confirmed_by": "利用者", "confirmation": "質問一覧全体と対話終了を確認した",
                "dialogue_complete": True,
            }
        return value

    def write(self, path: Path, value: dict) -> None:
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def check_temporary(self, artifact: dict) -> subprocess.CompletedProcess[str]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "artifact.json"
        self.write(path, artifact)
        return self.call(SCRIPT, "check", "--file", path.resolve())

    def test_success_artifact_is_accepted_without_stderr(self) -> None:
        result = self.check_temporary(self.load("success.json"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")

    def test_resolved_withdrawn_and_confirmation_are_distinct(self) -> None:
        artifact = self.load("success.json")
        artifact["open_questions"] = [
            {"id": "OQ-WL-998", "question": "解決済み", "owner": "利用者", "affected_refs": ["WL-001.average_rate"], "blocks": ["quality"], "state": "resolved", "resolution": "確定値", "reason": "合意済み"},
            {"id": "OQ-WL-999", "question": "撤回済み", "owner": "利用者", "affected_refs": ["WL-001.average_rate"], "blocks": ["quality"], "state": "withdrawn", "resolution": None, "reason": "対象外と合意"},
        ]
        artifact["question_review"]["question_ids"] = ["OQ-WL-998", "OQ-WL-999"]
        self.assertEqual(self.check_temporary(artifact).returncode, 0)
        artifact["open_questions"][1]["resolution"] = "誤った解決扱い"
        self.assertEqual(self.check_temporary(artifact).returncode, 2)

    def test_success_covers_average_peak_burst_growth_and_skew(self) -> None:
        artifact = self.load("success.json")
        workload = artifact["workload_items"][0]
        metrics = workload["characteristics"]
        self.assertEqual(metrics["average_rate"]["status"], "confirmed")
        self.assertEqual(metrics["peak_rate"]["status"], "confirmed")
        self.assertEqual(metrics["burst_rate"]["status"], "confirmed")
        self.assertEqual(metrics["growth_rate"]["status"], "hypothesis")
        self.assertEqual(workload["distribution"]["shape"], "skewed")
        design_input = artifact["design_inputs"][0]
        self.assertEqual(design_input["applicability"], "implementation_acceptance")
        self.assertIn("REQ-ORDER-001", design_input["requirement_refs"])
        self.assertIn("capacity", design_input["architecture_concerns"])

    def test_schema_one_is_rejected_without_migration_path(self) -> None:
        artifact = self.load("success.json")
        artifact["schema_version"] = 1
        del artifact["design_inputs"]
        del artifact["terminology"]
        artifact["handoff"]["downstream"]["cloud_design"].remove("DIN-001")
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("schema_versionは2", result.stderr)

    def test_schema_two_rejects_research_without_design_connection(self) -> None:
        artifact = self.load("success.json")
        del artifact["design_inputs"][0]["requirement_refs"]
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("requirement_refs", result.stderr)

    def test_fixture_matrix_fixes_success_out_of_scope_and_boundary(self) -> None:
        data = self.load("cases.json")
        scenarios = data["scenarios"]
        self.assertEqual(
            {scenario["kind"] for scenario in scenarios},
            {"success", "out_of_scope", "boundary"},
        )
        out_of_scope = next(
            scenario for scenario in scenarios if scenario["kind"] == "out_of_scope"
        )
        self.assertEqual(out_of_scope["expected"]["decision"], "stop_and_route")
        self.assertIsNone(out_of_scope["expected"]["artifact_fixture"])
        boundary = next(
            scenario for scenario in scenarios if scenario["kind"] == "boundary"
        )
        self.assertEqual(boundary["expected"]["base_status"], "confirmed")
        self.assertEqual(boundary["expected"]["changed_status"], "unresolved")
        self.assertIsNone(boundary["expected"]["changed_value"])

    def test_estimate_without_public_value_is_a_hypothesis_with_formula_confidence_and_verification(self) -> None:
        # 正例: 公開値が無い指標を、式・入力・確からしさ・検証計画・設計感度付きの仮説として持つ。
        artifact = self.load("success.json")
        growth = artifact["workload_items"][0]["characteristics"]["growth_rate"]
        self.assertEqual(growth["status"], "hypothesis")
        self.assertTrue(growth["calculation"])
        self.assertNotEqual(growth["confidence"], "unknown")
        self.assertTrue(growth["verification_plan"])
        self.assertTrue(growth["sensitivity"])
        self.assertEqual(self.check_temporary(artifact).returncode, 0)

        # 反例: 式が無い推定値を仮説として受理しない。
        no_formula = self.load("success.json")
        no_formula["workload_items"][0]["characteristics"]["growth_rate"]["calculation"] = ""
        result = self.check_temporary(no_formula)
        self.assertEqual(result.returncode, 2)
        self.assertIn("calculation", result.stderr)

        # 境界例: 確からしさがunknownの推定は仮説にならない。
        unknown_confidence = self.load("success.json")
        unknown_confidence["workload_items"][0]["characteristics"]["growth_rate"]["confidence"] = "unknown"
        result = self.check_temporary(unknown_confidence)
        self.assertEqual(result.returncode, 2)
        self.assertIn("confidence", result.stderr)

    def test_missing_time_window_is_valid_only_when_metric_becomes_unresolved(self) -> None:
        artifact = self.load("success.json")
        average = artifact["workload_items"][0]["characteristics"]["average_rate"]
        average.update(
            {
                "status": "unresolved",
                "value": None,
                "time_window": None,
                "confidence": "unknown",
                "calculation": None,
                "open_question_ids": ["OQ-WL-001"],
            }
        )
        artifact["open_questions"] = [
            {
                "id": "OQ-WL-001",
                "question": "日次件数を集計した対象期間はいつか",
                "owner": "計測責任者",
                "affected_refs": ["WL-001.average_rate"],
                "blocks": ["quality", "cloud_design"],
                "state": "open",
                "resolution": None,
                "reason": "回答待ち",
            }
        ]
        artifact["question_review"]["question_ids"] = ["OQ-WL-001"]
        artifact["artifact"]["state"] = "saved_with_open_questions"
        artifact["handoff"]["ready"] = False
        artifact["handoff"]["blocking_question_ids"] = ["OQ-WL-001"]
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 0, result.stderr)

        invalid = copy.deepcopy(artifact)
        invalid_average = invalid["workload_items"][0]["characteristics"]["average_rate"]
        invalid_average["status"] = "confirmed"
        invalid_average["value"] = 1
        invalid_average["confidence"] = "high"
        invalid_average["calculation"] = "86400 / 86400"
        result = self.check_temporary(invalid)
        self.assertEqual(result.returncode, 2)
        self.assertIn("time_window", result.stderr)

    def test_missing_numeric_context_cannot_remain_confirmed(self) -> None:
        changes = (
            ("unit", None, "unit"),
            ("time_window", None, "time_window"),
            ("population", None, "population"),
            ("claim_ids", [], "claim_ids"),
            ("confidence", "unknown", "confidence"),
        )
        for field, value, message in changes:
            with self.subTest(field=field):
                artifact = self.load("success.json")
                average = artifact["workload_items"][0]["characteristics"][
                    "average_rate"
                ]
                average[field] = value
                result = self.check_temporary(artifact)
                self.assertEqual(result.returncode, 2)
                self.assertIn(message, result.stderr)

    def test_average_claim_cannot_be_reused_as_peak_evidence(self) -> None:
        artifact = self.load("success.json")
        peak = artifact["workload_items"][0]["characteristics"]["peak_rate"]
        peak["claim_ids"] = ["CLM-002"]
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("別characteristic", result.stderr)

    def test_hypothesis_cannot_be_promoted_to_confirmed_growth(self) -> None:
        artifact = self.load("success.json")
        growth = artifact["workload_items"][0]["characteristics"]["growth_rate"]
        growth["status"] = "confirmed"
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("hypothesisをconfirmedへ昇格", result.stderr)

    def test_fan_out_and_hot_key_reject_technology_decision_fields(self) -> None:
        for metric_name, field in (
            ("fan_out", "queue_service"),
            ("hot_key_share", "partition_strategy"),
        ):
            with self.subTest(metric=metric_name):
                artifact = self.load("success.json")
                metric = artifact["workload_items"][0]["characteristics"][metric_name]
                metric[field] = "implementation-choice"
                result = self.check_temporary(artifact)
                self.assertEqual(result.returncode, 2)
                self.assertIn("keysが不正", result.stderr)

    def test_read_write_fraction_must_share_context_and_sum_to_one(self) -> None:
        artifact = self.load("success.json")
        write = artifact["workload_items"][0]["characteristics"]["write_share"]
        write["value"] = 0.4
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("fraction合計が1", result.stderr)

    def test_write_refuses_implicit_overwrite_and_accepts_next_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repo = base / "repository"
            repo.mkdir()
            source = base / "source.json"
            self.write(source, self.load("success.json"))
            first = self.call(
                SCRIPT,
                "write",
                "--repo",
                repo.resolve(),
                "--slug",
                "order-submitted",
                "--file",
                source,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stderr, "")

            duplicate = self.call(
                SCRIPT,
                "write",
                "--repo",
                repo.resolve(),
                "--slug",
                "order-submitted",
                "--file",
                source,
            )
            self.assertEqual(duplicate.returncode, 2)
            self.assertIn("--expected-version", duplicate.stderr)

            update = self.load("success.json")
            update["artifact"]["version"] = 2
            update["change_log"].append(
                {
                    "version": 2,
                    "changed_input_ids": ["SRC-001"],
                    "invalidated_refs": ["WL-001.peak_rate"],
                    "summary": "peak観測窓を再集計",
                }
            )
            update_path = base / "update.json"
            self.write(update_path, update)
            replaced = self.call(
                SCRIPT,
                "write",
                "--repo",
                repo.resolve(),
                "--slug",
                "order-submitted",
                "--file",
                update_path.resolve(),
                "--expected-version",
                "1",
            )
            self.assertEqual(replaced.returncode, 0, replaced.stderr)
            target = repo / "system-design/workloads/order-submitted.workload.json"
            self.assertEqual(json.loads(target.read_text())["artifact"]["version"], 2)

    def test_distribution_copy_has_no_source_checkout_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            copied = base / "system-design"
            shutil.copytree(ROOT / "plugins/system-design", copied)
            artifact = base / "workload.json"
            self.write(artifact, self.load("success.json"))
            copied_script = copied / "skills/discover-workload-model/scripts/workload.py"
            result = self.call(
                copied_script,
                "check",
                "--file",
                artifact.resolve(),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
