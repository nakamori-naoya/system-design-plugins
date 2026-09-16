#!/usr/bin/env python3
"""Regression tests for design-cloud-architecture behavior."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "plugins/system-design"
SKILL_ROOT = PACKAGE_ROOT / "skills/design-cloud-architecture"
SCRIPT = SKILL_ROOT / "scripts/architecture.py"
FIXTURES = ROOT / "tests/fixtures/design-cloud-architecture"
CAPABILITIES = {
    "provider", "region_az", "compute", "network", "storage", "database",
    "messaging", "identity", "edge", "observability", "backup_dr", "delivery",
}


class ArchitectureContractTest(unittest.TestCase):
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

    def test_withdrawn_question_does_not_block_ready_but_requires_final_confirmation(self) -> None:
        artifact = self.load("success.json")
        artifact["open_questions"] = [{"id": "OQ-ARCH-999", "question": "撤回済み", "owner": "利用者", "affected_refs": ["SEL-001"], "blocks": ["implementation_handoff"], "state": "withdrawn", "resolution": None, "reason": "対象外と合意"}]
        artifact["question_review"]["question_ids"] = ["OQ-ARCH-999"]
        self.assertEqual(self.check_temporary(artifact).returncode, 0)
        artifact["question_review"]["question_ids"] = []
        self.assertEqual(self.check_temporary(artifact).returncode, 2)

    def test_schema_one_is_rejected_without_migration_path(self) -> None:
        artifact = self.load("success.json")
        artifact["schema_version"] = 1
        del artifact["terminology"]
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("schema_versionは2", result.stderr)

    def test_success_contains_required_design_products(self) -> None:
        artifact = self.load("success.json")
        self.assertEqual(
            {item["category"] for item in artifact["selections"]},
            CAPABILITIES,
        )
        self.assertGreaterEqual(len(artifact["alternatives"]), 2)
        self.assertTrue(any(item["status"] == "accepted" for item in artifact["adrs"]))
        self.assertTrue(artifact["diagram"]["editable"])
        self.assertTrue(artifact["diagram"]["source"].startswith("flowchart"))
        self.assertTrue(artifact["traceability"])
        self.assertTrue(artifact["failure_scenarios"])
        self.assertTrue(artifact["verification_plan"])

    def test_input_provider_is_traced_to_an_agreed_constraint_and_mismatches_are_rejected(self) -> None:
        # 正例: 入力providerは合意済み制約（CON-）へ辿れ、provider選定がその制約を引用する。
        artifact = self.load("success.json")
        decision = artifact["provider_decision"]
        constraint = next(item for item in artifact["constraints"] if item["id"] == decision["constraint_id"])
        provider_selection = next(
            item for item in artifact["selections"] if item["category"] == "provider"
        )
        self.assertEqual(decision["provider"], "aws")
        self.assertEqual(constraint["classification"], "agreed_decision")
        self.assertEqual(provider_selection["provider"], "aws")
        self.assertIn(decision["constraint_id"], provider_selection["constraint_ids"])

        # 反例: aws/gcp以外のprovider。
        invalid_provider = self.load("success.json")
        invalid_provider["provider_decision"]["provider"] = "azure"
        result = self.check_temporary(invalid_provider)
        self.assertEqual(result.returncode, 2)
        self.assertIn("awsまたはgcp", result.stderr)

        # 反例: 存在しない制約ID。
        unknown_constraint = self.load("success.json")
        unknown_constraint["provider_decision"]["constraint_id"] = "CON-999"
        result = self.check_temporary(unknown_constraint)
        self.assertEqual(result.returncode, 2)
        self.assertIn("constraintsに存在しません", result.stderr)

        # 反例: 仮説の制約をprovider根拠にする。
        hypothesis_constraint = self.load("success.json")
        hypothesis_constraint["provider_decision"]["constraint_id"] = "CON-003"
        result = self.check_temporary(hypothesis_constraint)
        self.assertEqual(result.returncode, 2)
        self.assertIn("agreed_decision", result.stderr)

        # 反例: 旧形の来歴keyは受理しない。
        legacy_shape = self.load("success.json")
        legacy_shape["provider_decision"] = {
            "provider": "aws",
            "source_artifact_id": "SRC-008",
            "config_locator": "/evidence/system-design.config.yml",
            "config_fingerprint": "sha256:provider-aws-001",
        }
        result = self.check_temporary(legacy_shape)
        self.assertEqual(result.returncode, 2)
        self.assertIn("keys", result.stderr)

        # 反例: provider公開入力化より前の正本（top-level provider_resolution）は、
        # schema_version 2のままでも、何が変わったかを示す診断で拒否する。
        pre_change = self.load("success.json")
        pre_change["provider_resolution"] = pre_change.pop("provider_decision")
        result = self.check_temporary(pre_change)
        self.assertEqual(result.returncode, 2)
        self.assertIn("provider公開入力化より前の形", result.stderr)
        self.assertIn("provider_decision", result.stderr)

        # 反例: provider選定のproviderが入力providerと違う。
        mismatch = self.load("success.json")
        next(item for item in mismatch["selections"] if item["category"] == "provider")[
            "provider"
        ] = "gcp"
        result = self.check_temporary(mismatch)
        self.assertEqual(result.returncode, 2)
        self.assertIn("入力provider", result.stderr)

        # 境界例: 制約は存在するがprovider選定が引用しない。
        untraced = self.load("success.json")
        selection = next(
            item for item in untraced["selections"] if item["category"] == "provider"
        )
        selection["constraint_ids"].remove("CON-004")
        result = self.check_temporary(untraced)
        self.assertEqual(result.returncode, 2)
        self.assertIn("provider constraint", result.stderr)

    def test_fixture_matrix_covers_deployment_boundaries(self) -> None:
        scenarios = self.load("cases.json")["scenarios"]
        self.assertEqual(
            {scenario["kind"] for scenario in scenarios},
            {"success", "out_of_scope", "boundary"},
        )
        boundary_modes = {
            scenario["expected"]["changed_mode"]
            for scenario in scenarios
            if scenario["kind"] == "boundary"
        }
        self.assertEqual(
            boundary_modes,
            {"multi_cloud", "hybrid", "on_prem", "cloud_undecided"},
        )
        success = next(
            scenario for scenario in scenarios if scenario["kind"] == "success"
        )
        self.assertEqual(success["input"]["provider"], "aws")
        self.assertEqual(success["expected"]["provider"], "aws")
        self.assertEqual(success["expected"]["provider_constraint_id"], "CON-004")
        undecided = next(
            scenario
            for scenario in scenarios
            if scenario["id"] == "cloud-undecided-boundary"
        )
        self.assertEqual(undecided["expected"]["state"], "saved_with_open_questions")
        self.assertEqual(undecided["expected"]["must_not"], "人気だけでプロバイダーを選ばない")

    def test_selected_service_requires_all_grounding_dimensions(self) -> None:
        fields = (
            "requirement_driver_ids",
            "quality_driver_ids",
            "workload_driver_ids",
            "constraint_ids",
            "alternative_ids",
            "adr_ids",
            "verification_ids",
        )
        for field in fields:
            with self.subTest(field=field):
                artifact = self.load("success.json")
                artifact["selections"][0][field] = []
                result = self.check_temporary(artifact)
                self.assertEqual(result.returncode, 2)
                self.assertIn(field, result.stderr)

    def test_popular_provider_list_without_grounding_is_rejected(self) -> None:
        artifact = self.load("success.json")
        provider = artifact["selections"][0]
        provider["rationale"] = "popular provider and standard service"
        provider["quality_driver_ids"] = []
        provider["workload_driver_ids"] = []
        provider["constraint_ids"] = []
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("quality_driver_ids", result.stderr)

    def test_traceability_must_match_selection(self) -> None:
        artifact = self.load("success.json")
        artifact["traceability"][0]["workload_driver_ids"] = []
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("traceability.workload_driver_ids", result.stderr)

    def test_diagram_exposes_boundary_flow_dependency_and_availability(self) -> None:
        artifact = self.load("success.json")
        diagram = artifact["diagram"]
        self.assertEqual(
            {item["kind"] for item in diagram["boundaries"]},
            {"system", "trust_zone", "external"},
        )
        self.assertEqual({item["synchrony"] for item in diagram["flows"]}, {"sync", "async"})
        self.assertTrue(any(item["trust_boundary_crossing"] for item in diagram["flows"]))
        self.assertTrue(diagram["external_dependencies"])
        self.assertTrue(diagram["availability_units"])

    def test_missing_diagram_semantics_are_rejected(self) -> None:
        mutations = []

        no_external = self.load("success.json")
        no_external["diagram"]["external_dependencies"] = []
        mutations.append((no_external, "external_dependencies"))

        no_async = self.load("success.json")
        for flow in no_async["diagram"]["flows"]:
            flow["synchrony"] = "sync"
        mutations.append((no_async, "syncとasync"))

        no_crossing = self.load("success.json")
        for flow in no_crossing["diagram"]["flows"]:
            flow["trust_boundary_crossing"] = False
        mutations.append((no_crossing, "trust_boundary_crossing"))

        missing_source_id = self.load("success.json")
        missing_source_id["diagram"]["source"] = missing_source_id["diagram"]["source"].replace(
            "FLW-005", "FLOW-FIVE"
        )
        mutations.append((missing_source_id, "FLW-005"))

        comment_only_availability = self.load("success.json")
        comment_only_availability["diagram"]["source"] = comment_only_availability[
            "diagram"
        ]["source"].replace(
            'subgraph AU001["AU-001 リージョン入口単位"]',
            'subgraph HIDDEN001["リージョン入口単位"]\n      %% AU-001 リージョン入口単位',
        )
        mutations.append(
            (comment_only_availability, "表示可用性単位")
        )

        missing_display_node = self.load("success.json")
        missing_display_node["diagram"]["source"] = missing_display_node["diagram"]["source"].replace(
            'NOD006["NOD-006 データベース"]',
            '%% NOD-006 データベース',
        )
        mutations.append((missing_display_node, "表示ノード"))

        wrong_display_endpoint = self.load("success.json")
        wrong_display_endpoint["diagram"]["source"] = wrong_display_endpoint["diagram"]["source"].replace(
            'NOD013 -->|"FLW-001', 'NOD012 -->|"FLW-001',
        )
        mutations.append((wrong_display_endpoint, "表示フロー接続先"))

        wrong_display_synchrony = self.load("success.json")
        wrong_display_synchrony["diagram"]["source"] = wrong_display_synchrony["diagram"]["source"].replace(
            'FLW-004 変更イベント / 非同期', 'FLW-004 変更イベント / 同期',
        )
        mutations.append((wrong_display_synchrony, "表示フロー種別"))

        for artifact, message in mutations:
            with self.subTest(message=message):
                result = self.check_temporary(artifact)
                self.assertEqual(result.returncode, 2)
                self.assertIn(message, result.stderr)

    def test_deployment_mode_provider_scope_boundaries_are_enforced(self) -> None:
        changes = (
            ("single_cloud", ["aws", "gcp"]),
            ("multi_cloud", ["aws"]),
            ("on_prem", ["aws"]),
            ("cloud_undecided", ["aws"]),
        )
        for mode, providers in changes:
            with self.subTest(mode=mode):
                artifact = self.load("success.json")
                artifact["deployment_model"]["mode"] = mode
                artifact["deployment_model"]["provider_scope"] = providers
                result = self.check_temporary(artifact)
                self.assertEqual(result.returncode, 2)
                self.assertIn("provider_scope", result.stderr)

    def test_cloud_undecided_cannot_keep_selected_services(self) -> None:
        artifact = self.load("success.json")
        artifact["deployment_model"].update(
            {
                "mode": "cloud_undecided",
                "provider_scope": [],
                "decision_state": "unresolved",
                "alternative_id": None,
                "open_question_ids": ["OQ-ARCH-001"],
            }
        )
        chosen = next(item for item in artifact["alternatives"] if item["status"] == "chosen")
        chosen["status"] = "deferred"
        chosen["rejection_reason"] = "provider decision is open"
        artifact["open_questions"] = [
            {
                "id": "OQ-ARCH-001",
                "question": "which provider constraints are agreed",
                "owner": "architecture sponsor",
                "affected_refs": ["SEL-001", "ALT-001"],
                "blocks": ["implementation_handoff"],
                "state": "open",
                "resolution": None,
                "reason": "回答待ち",
            }
        ]
        artifact["question_review"]["question_ids"] = ["OQ-ARCH-001"]
        artifact["artifact"]["state"] = "saved_with_open_questions"
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("cloud_undecidedでserviceをselected", result.stderr)

    def test_cloud_undecided_saves_candidate_design_as_not_ready(self) -> None:
        artifact = self.load("success.json")
        artifact["artifact"]["state"] = "saved_with_open_questions"
        artifact["deployment_model"].update(
            {
                "mode": "cloud_undecided",
                "provider_scope": [],
                "decision_state": "unresolved",
                "alternative_id": None,
                "open_question_ids": ["OQ-ARCH-001"],
            }
        )
        for alternative in artifact["alternatives"]:
            alternative["status"] = "deferred"
            if alternative["rejection_reason"] is None:
                alternative["rejection_reason"] = "provider decision is open"
        for selection in artifact["selections"]:
            selection["status"] = "unresolved"
            selection["choice"] = None
            selection["provider"] = None
            selection["service"] = None
            selection["open_question_ids"] = ["OQ-ARCH-001"]
        artifact["adrs"][0]["status"] = "proposed"
        for node in artifact["diagram"]["nodes"]:
            if node["kind"] == "component":
                node["kind"] = "candidate"
        artifact["traceability"] = []
        artifact["open_questions"] = [
            {
                "id": "OQ-ARCH-001",
                "question": "which provider and service constraints are agreed",
                "owner": "architecture sponsor",
                "affected_refs": ["SEL-001", "ALT-001"],
                "blocks": ["implementation_handoff"],
                "state": "open",
                "resolution": None,
                "reason": "回答待ち",
            }
        ]
        artifact["question_review"]["question_ids"] = ["OQ-ARCH-001"]
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_adr_requires_comparison_and_negative_tradeoff(self) -> None:
        artifact = self.load("success.json")
        artifact["adrs"][0]["alternative_ids"] = ["ALT-001"]
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("比較のため2件以上", result.stderr)

        artifact = self.load("success.json")
        artifact["adrs"][0]["negative_consequences"] = []
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("negative_consequences", result.stderr)

    def test_planned_verification_cannot_claim_passed_without_evidence(self) -> None:
        artifact = self.load("success.json")
        artifact["verification_plan"][0]["status"] = "passed"
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("evidence_refs", result.stderr)

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
                    "changed_input_ids": ["SRC-003"],
                    "invalidated_refs": ["SEL-003", "ADR-001", "VER-001"],
                    "summary": "workload version changed",
                }
            )
            update_path = base / "update.json"
            self.write(update_path, update)
            replaced = self.call(
                SCRIPT, "write", "--repo", repo.resolve(), "--slug", "status",
                "--file", update_path.resolve(), "--expected-version", "1",
            )
            self.assertEqual(replaced.returncode, 0, replaced.stderr)
            target = repo / "system-design/architectures/status.architecture.json"
            self.assertEqual(json.loads(target.read_text())["artifact"]["version"], 2)

    def test_package_copy_has_no_source_checkout_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            copied = base / "system-design"
            shutil.copytree(ROOT / "plugins/system-design", copied)
            artifact = base / "architecture.json"
            self.write(artifact, self.load("success.json"))
            copied_script = copied / "skills/design-cloud-architecture/scripts/architecture.py"
            result = self.call(copied_script, "check", "--file", artifact.resolve())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
