#!/usr/bin/env python3
"""Regression tests for discover-quality-requirements behavior."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "plugins/system-design/skills/discover-quality-requirements"
SCRIPT = SKILL_ROOT / "scripts/quality.py"
FIXTURES = ROOT / "tests/fixtures/discover-quality-requirements"
CATEGORIES = {
    "latency",
    "throughput",
    "availability",
    "consistency",
    "durability",
    "recovery",
    "security",
    "privacy",
    "operability",
    "cost",
}


class QualityContractTest(unittest.TestCase):
    def call(self, script: Path, *arguments: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(script), *[str(argument) for argument in arguments]],
            text=True,
            capture_output=True,
            check=False,
        )

    def load(self, name: str) -> dict:
        value = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        if name == "success.json":
            value["schema_version"] = 2
        if value.get("schema_version") == 2:
            for item in value["open_questions"]:
                item.update(state="open", resolution=None, reason="未決として一覧確認した")
            value["question_review"] = {
                "question_ids": [item["id"] for item in value["open_questions"]],
                "confirmed_by": "利用者", "confirmation": "質問一覧全体と対話終了を確認した",
                "dialogue_complete": True,
            }
        return value

    def test_question_review_must_cover_the_whole_list(self) -> None:
        artifact = self.load("success.json")
        artifact["open_questions"] = [{"id": "OQ-QR-999", "question": "未決", "owner": "利用者", "affected_refs": ["QR-001"], "blocks": ["architecture"], "state": "open", "resolution": None, "reason": "回答待ち"}]
        artifact["handoff"]["ready"] = False
        artifact["handoff"]["blocking_question_ids"] = ["OQ-QR-999"]
        artifact["artifact"]["state"] = "saved_with_open_questions"
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("質問一覧全体", result.stderr)

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

    def test_preserved_schema_one_fixture_is_rejected(self) -> None:
        path = (FIXTURES / "success.json").resolve()
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["schema_version"], 1)
        result = self.call(SCRIPT, "check", "--file", path)
        self.assertEqual(result.returncode, 2)
        self.assertIn("schema_versionは2", result.stderr)

    def test_success_covers_categories_measurement_and_hypotheses(self) -> None:
        artifact = self.load("success.json")
        self.assertEqual(
            {item["category"] for item in artifact["category_coverage"]},
            CATEGORIES,
        )
        by_id = {item["id"]: item for item in artifact["quality_requirements"]}
        for item in by_id.values():
            self.assertIsNotNone(item["observation_point"])
            self.assertIsNotNone(item["metric"])
            self.assertIsNotNone(item["threshold"])
            self.assertIsNotNone(item["time_window"])
            self.assertIsNotNone(item["population"])
            self.assertIsNotNone(item["verification_method"])
        self.assertEqual(by_id["QR-002"]["status"], "hypothesis")
        self.assertEqual(by_id["QR-006"]["status"], "hypothesis")
        links = {item["id"]: item for item in artifact["workload_links"]}
        self.assertEqual(links["QWL-001"]["workload_status"], "hypothesis")
        self.assertEqual(links["QWL-001"]["relation"], "assumption")
        self.assertEqual(artifact["conflicts"][0]["status"], "resolved")

    def test_fixture_matrix_has_success_out_of_scope_and_boundary(self) -> None:
        scenarios = self.load("cases.json")["scenarios"]
        self.assertEqual(
            {scenario["kind"] for scenario in scenarios},
            {"success", "out_of_scope", "boundary"},
        )
        out_of_scope = next(
            scenario for scenario in scenarios if scenario["kind"] == "out_of_scope"
        )
        self.assertEqual(out_of_scope["expected"]["decision"], "stop_and_route")
        vague = next(
            scenario
            for scenario in scenarios
            if scenario["id"] == "quality-vague-boundary"
        )
        self.assertEqual(vague["expected"]["changed_status"], "unresolved")
        self.assertIsNone(vague["expected"]["changed_threshold"])

    def test_vague_high_availability_is_valid_only_as_unresolved(self) -> None:
        artifact = self.load("success.json")
        availability = next(
            item for item in artifact["quality_requirements"] if item["id"] == "QR-003"
        )
        availability.update(
            {
                "title": "高可用",
                "status": "unresolved",
                "observation_point": None,
                "metric": None,
                "threshold": None,
                "time_window": None,
                "population": None,
                "verification_method": None,
                "verification_owner": None,
                "confidence": "unknown",
                "open_question_ids": ["OQ-QR-001"],
            }
        )
        coverage = next(
            item
            for item in artifact["category_coverage"]
            if item["category"] == "availability"
        )
        coverage["disposition"] = "unresolved"
        coverage["open_question_ids"] = ["OQ-QR-001"]
        artifact["open_questions"] = [
            {
                "id": "OQ-QR-001",
                "question": "高可用の観測点、metric、閾値、時間窓、母集団は何か",
                "owner": "service owner",
                "affected_refs": ["QR-003"],
                "blocks": ["architecture"],
                "state": "open",
                "resolution": None,
                "reason": "回答待ち",
            }
        ]
        artifact["question_review"]["question_ids"] = ["OQ-QR-001"]
        artifact["artifact"]["state"] = "saved_with_open_questions"
        artifact["handoff"]["ready"] = False
        artifact["handoff"]["blocking_question_ids"] = ["OQ-QR-001"]
        artifact["handoff"]["quality_requirement_ids"].remove("QR-003")
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 0, result.stderr)

        invalid = copy.deepcopy(artifact)
        invalid_availability = next(
            item for item in invalid["quality_requirements"] if item["id"] == "QR-003"
        )
        invalid_availability["status"] = "agreed"
        result = self.check_temporary(invalid)
        self.assertEqual(result.returncode, 2)
        self.assertIn("observation_point", result.stderr)

    def test_missing_measurement_field_cannot_remain_agreed(self) -> None:
        changes = (
            ("observation_point", None, "observation_point"),
            ("metric", None, "metric"),
            ("threshold", None, "threshold"),
            ("time_window", None, "time_window"),
            ("population", None, "population"),
            ("verification_method", None, "verification_method"),
        )
        for field, value, message in changes:
            with self.subTest(field=field):
                artifact = self.load("success.json")
                latency = artifact["quality_requirements"][0]
                latency[field] = value
                result = self.check_temporary(artifact)
                self.assertEqual(result.returncode, 2)
                self.assertIn(message, result.stderr)

    def test_unagreed_numeric_threshold_cannot_be_promoted(self) -> None:
        artifact = self.load("success.json")
        throughput = next(
            item for item in artifact["quality_requirements"] if item["id"] == "QR-002"
        )
        throughput["status"] = "agreed"
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("合意済み品質閾値の根拠", result.stderr)

    def test_workload_hypothesis_cannot_be_promoted_to_support(self) -> None:
        artifact = self.load("success.json")
        link = next(item for item in artifact["workload_links"] if item["id"] == "QWL-001")
        link["relation"] = "supports"
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("未確認workloadをsupportsへ昇格", result.stderr)

    def test_missing_workload_model_cannot_be_ready(self) -> None:
        artifact = self.load("success.json")
        artifact["input_artifacts"] = [
            item for item in artifact["input_artifacts"] if item["kind"] != "workload"
        ]
        workload_claim = next(
            item for item in artifact["claims"] if item["source_artifact_id"] == "SRC-004"
        )
        workload_claim["source_artifact_id"] = "SRC-005"
        artifact["workload_links"] = []
        artifact["conflicts"] = []
        for quality in artifact["quality_requirements"]:
            quality["workload_link_ids"] = []
            quality["conflict_ids"] = []
        artifact["handoff"]["workload_link_ids"] = []
        artifact["handoff"]["conflict_ids"] = []
        artifact["change_log"][0]["changed_input_ids"].remove("SRC-004")
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("workload modelがない場合は未決", result.stderr)

    def test_conflicting_workload_requires_traceable_conflict(self) -> None:
        artifact = self.load("success.json")
        link = next(item for item in artifact["workload_links"] if item["id"] == "QWL-004")
        link["conflict_ids"] = []
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("conflict_ids", result.stderr)

        artifact = self.load("success.json")
        quality = next(
            item for item in artifact["quality_requirements"] if item["id"] == "QR-006"
        )
        quality["conflict_ids"] = []
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("逆参照", result.stderr)

    def test_open_conflict_forces_saved_not_ready_state(self) -> None:
        artifact = self.load("success.json")
        conflict = artifact["conflicts"][0]
        conflict.update(
            {
                "status": "open",
                "resolution": None,
                "evidence_claim_ids": [],
                "open_question_ids": ["OQ-QR-001"],
            }
        )
        artifact["open_questions"] = [
            {
                "id": "OQ-QR-001",
                "question": "launch peak時の月額費用を再現できるか",
                "owner": "product finance owner",
                "affected_refs": ["QR-006", "QWL-004", "QCON-001"],
                "blocks": ["architecture"],
                "state": "open",
                "resolution": None,
                "reason": "回答待ち",
            }
        ]
        artifact["question_review"]["question_ids"] = ["OQ-QR-001"]
        artifact["artifact"]["state"] = "saved_with_open_questions"
        artifact["handoff"]["ready"] = False
        artifact["handoff"]["blocking_question_ids"] = ["OQ-QR-001"]
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 0, result.stderr)

        invalid = copy.deepcopy(artifact)
        invalid["artifact"]["state"] = "ready_for_architecture"
        invalid["handoff"]["ready"] = True
        invalid["handoff"]["blocking_question_ids"] = []
        result = self.check_temporary(invalid)
        self.assertEqual(result.returncode, 2)
        self.assertIn("blocking_question_ids", result.stderr)

    def test_resolved_conflict_cannot_rely_on_hypothesis_only(self) -> None:
        artifact = self.load("success.json")
        claim = next(item for item in artifact["claims"] if item["id"] == "CLM-007")
        claim["classification"] = "hypothesis"
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("hypothesisだけでresolved", result.stderr)

    def test_cloud_product_field_is_rejected(self) -> None:
        artifact = self.load("success.json")
        artifact["quality_requirements"][0]["cloud_service"] = "managed product"
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("keysが不正", result.stderr)

    def test_write_refuses_implicit_overwrite_and_accepts_next_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repo = base / "repository"
            repo.mkdir()
            source = base / "source.json"
            self.write(source, self.load("success.json"))
            first = self.call(
                SCRIPT, "write", "--repo", repo.resolve(), "--slug", "status", "--file", source
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stderr, "")

            duplicate = self.call(
                SCRIPT, "write", "--repo", repo.resolve(), "--slug", "status", "--file", source
            )
            self.assertEqual(duplicate.returncode, 2)
            self.assertIn("--expected-version", duplicate.stderr)

            update = self.load("success.json")
            update["artifact"]["version"] = 2
            update["change_log"].append(
                {
                    "version": 2,
                    "changed_input_ids": ["SRC-004"],
                    "invalidated_refs": ["QR-002", "QWL-002"],
                    "summary": "launch peak hypothesis source updated",
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
                "status",
                "--file",
                update_path.resolve(),
                "--expected-version",
                "1",
            )
            self.assertEqual(replaced.returncode, 0, replaced.stderr)
            target = repo / "system-design/quality-requirements/status.quality.json"
            self.assertEqual(json.loads(target.read_text())["artifact"]["version"], 2)

    def test_package_copy_has_no_source_checkout_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            copied = base / "system-design"
            shutil.copytree(ROOT / "plugins/system-design", copied)
            artifact = base / "quality.json"
            self.write(artifact, self.load("success.json"))
            copied_script = copied / "skills/discover-quality-requirements/scripts/quality.py"
            result = self.call(copied_script, "check", "--file", artifact.resolve())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
