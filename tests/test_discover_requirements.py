#!/usr/bin/env python3
"""Regression tests for discover-requirements artifact behavior."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "plugins/system-design/skills/discover-requirements"
SCRIPT = SKILL_ROOT / "scripts/requirements.py"
FIXTURES = ROOT / "tests/fixtures/discover-requirements"


class RequirementsContractTest(unittest.TestCase):
    def call(self, script: Path, *arguments: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(script), *[str(argument) for argument in arguments]],
            text=True,
            capture_output=True,
            check=False,
        )

    def write_json(self, path: Path, value: dict) -> None:
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def load_fixture(self, name: str) -> dict:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def outcome(self, status: str = "not_applicable") -> dict:
        return {
            "status": status,
            "statement": None,
            "open_question_ids": [],
        }

    def command(
        self,
        identifier: str,
        name: str,
        event_id: str,
        counterpart_id: str | None = None,
        counterpart_review: str = "not_applicable",
    ) -> dict:
        return {
            "id": identifier,
            "name": name,
            "actor_ids": ["STK-001"],
            "claim_ids": ["CLM-002"],
            "state_target": "申請",
            "success_event_ids": [event_id],
            "counterpart_command_id": counterpart_id,
            "counterpart_review": counterpart_review,
            "counterpart_rationale": "業務上の対操作を確認した",
            "counterpart_open_question_ids": [],
            "non_success_outcomes": {
                "no_change": self.outcome(),
                "rejected": self.outcome(),
                "failed": self.outcome(),
            },
        }

    def business_event(
        self,
        identifier: str,
        name: str,
        before: str,
        after: str,
    ) -> dict:
        return {
            "id": identifier,
            "name": name,
            "claim_ids": ["CLM-002"],
            "completed_fact": f"申請が{after}になった",
            "state_target": "申請",
            "state_change": {"from": before, "to": after},
        }

    def test_success_and_boundary_artifacts_are_accepted(self) -> None:
        for name in ("success.json", "boundary.json"):
            with self.subTest(name=name):
                result = self.call(
                    SCRIPT,
                    "check",
                    "--file",
                    (FIXTURES / name).resolve(),
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertEqual(
                    result.stdout.strip(),
                    str((FIXTURES / name).resolve()),
                )

        self.assertEqual(self.load_fixture("success.json")["schema_version"], 2)
        self.assertEqual(self.load_fixture("boundary.json")["schema_version"], 1)

    def test_schema_two_requires_complete_causal_derived_requirement(self) -> None:
        artifact = self.load_fixture("success.json")
        derived = artifact["derived_requirements"][0]
        self.assertTrue(derived["service_characteristic"])
        self.assertTrue(derived["failure_risk"])
        self.assertTrue(derived["required_outcome"])
        self.assertTrue(derived["design_impacts"])
        self.assertTrue(derived["revisit_when"])

        invalid = copy.deepcopy(artifact)
        invalid["derived_requirements"][0]["failure_risk"] = ""
        result = self.check_temporary(invalid)
        self.assertEqual(result.returncode, 2)
        self.assertIn("failure_risk", result.stderr)

    def test_schema_two_rejects_duplicate_or_unresolved_term_usage(self) -> None:
        artifact = self.load_fixture("success.json")
        duplicate = copy.deepcopy(artifact)
        duplicate["terminology"]["usages"].append(
            copy.deepcopy(duplicate["terminology"]["usages"][0])
        )
        result = self.check_temporary(duplicate)
        self.assertEqual(result.returncode, 2)
        self.assertIn("subject_idが重複", result.stderr)

        unresolved = copy.deepcopy(artifact)
        unresolved["terminology"]["usages"][0]["subject_id"] = "REQ-999"
        result = self.check_temporary(unresolved)
        self.assertEqual(result.returncode, 2)
        self.assertIn("subject_idが未解決", result.stderr)

    def test_commands_trace_success_events_and_reciprocal_counterparts(self) -> None:
        artifact = self.load_fixture("success.json")
        artifact["interaction_catalog"]["command_events"].extend(
            [
                self.business_event("CEVT-002", "申請受付が開始された", "未受付", "受付中"),
                self.business_event("CEVT-003", "申請受付が解除された", "受付中", "未受付"),
            ]
        )
        artifact["interaction_catalog"]["commands"] = [
            self.command("CMD-001", "申請受付を開始する", "CEVT-002", "CMD-002", "paired"),
            self.command("CMD-002", "申請受付を解除する", "CEVT-003", "CMD-001", "paired"),
        ]
        artifact["terminology"]["usages"].append(
            {"subject_id": "CMD-001", "preferred_terms": ["申請受付を開始する"]}
        )
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 0, result.stderr)

        artifact["interaction_catalog"]["commands"][1]["counterpart_command_id"] = None
        artifact["interaction_catalog"]["commands"][1]["counterpart_review"] = "not_applicable"
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("相互参照", result.stderr)

    def test_unresolved_non_success_or_counterpart_requires_open_question(self) -> None:
        artifact = self.load_fixture("success.json")
        command = self.command("CMD-001", "申請を取り消す", "CEVT-001")
        command["non_success_outcomes"]["rejected"]["status"] = "unresolved"
        artifact["interaction_catalog"]["commands"] = [command]
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("open_question_ids", result.stderr)

        command["non_success_outcomes"]["rejected"] = self.outcome()
        command["counterpart_review"] = "unresolved"
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("counterpart_open_question_ids", result.stderr)

        artifact["claims"].append(
            {
                "id": "CLM-004",
                "statement": "取消の対操作と拒否時の扱いは未決である",
                "classification": "open_question",
                "source": "要求確認会議",
                "observed_at": "2026-09-14",
                "owner": "業務責任者",
            }
        )
        artifact["open_questions"] = [
            {
                "id": "OQ-001",
                "question": "取消の対操作と拒否時の業務結果をどうするか",
                "claim_ids": ["CLM-004"],
                "owner": "業務責任者",
                "affected_ids": ["CMD-001"],
                "blocks": ["domain"],
            }
        ]
        command["counterpart_open_question_ids"] = ["OQ-001"]
        command["non_success_outcomes"]["rejected"] = {
            "status": "unresolved",
            "statement": None,
            "open_question_ids": ["OQ-001"],
        }
        artifact["artifact"]["state"] = "saved_with_open_questions"
        artifact["handoff"]["ready"] = False
        artifact["handoff"]["blocking_question_ids"] = ["OQ-001"]
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_system_event_cannot_replace_business_success_event(self) -> None:
        artifact = self.load_fixture("success.json")
        artifact["interaction_catalog"]["system_events"] = [
            {
                "id": "SEVT-001",
                "name": "申請記録が保存された",
                "claim_ids": ["CLM-002"],
                "observed_fact": "内部の申請記録の永続化が完了した",
                "related_event_ids": ["CEVT-001"],
            }
        ]
        command = self.command("CMD-001", "申請結果を確定する", "CEVT-001")
        command["success_event_ids"] = ["SEVT-001"]
        artifact["interaction_catalog"]["commands"] = [command]
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("success_event_ids", result.stderr)

    def test_unconfirmed_operation_cannot_be_promoted_to_command_or_query(self) -> None:
        artifact = self.load_fixture("success.json")
        artifact["claims"].append(
            {
                "id": "CLM-004",
                "statement": "申請を取り消せるはず",
                "classification": "hypothesis",
                "source": "担当者の推測",
                "observed_at": "2026-09-14",
                "owner": "担当者",
            }
        )
        command = self.command("CMD-001", "申請を取り消す", "CEVT-001")
        command["claim_ids"] = ["CLM-004"]
        artifact["interaction_catalog"]["commands"] = [command]
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("コマンドへ昇格", result.stderr)

        artifact = self.load_fixture("success.json")
        artifact["claims"].append(
            {
                "id": "CLM-004",
                "statement": "申請履歴を参照するはず",
                "classification": "hypothesis",
                "source": "担当者の推測",
                "observed_at": "2026-09-14",
                "owner": "担当者",
            }
        )
        artifact["interaction_catalog"]["queries"][0]["claim_ids"] = ["CLM-004"]
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 2)
        self.assertIn("クエリへ昇格", result.stderr)

    def test_query_and_time_events_are_first_class_and_do_not_change_state(self) -> None:
        artifact = self.load_fixture("success.json")
        artifact["interaction_catalog"]["time_events"] = [
            {
                "id": "TEVT-001",
                "name": "申請保持期限に到達した",
                "claim_ids": ["CLM-002"],
                "occurred_fact": "申請結果の保持期限に到達した",
                "time_basis": "申請結果確定時点から合意済み保持期間が経過した時刻",
            }
        ]
        result = self.check_temporary(artifact)
        self.assertEqual(result.returncode, 0, result.stderr)

        invalid = copy.deepcopy(artifact)
        invalid["interaction_catalog"]["query_events"][0]["state_change"] = {
            "from": "未確認",
            "to": "確認済み",
        }
        result = self.check_temporary(invalid)
        self.assertEqual(result.returncode, 2)
        self.assertIn("state_change", result.stderr)

        invalid = copy.deepcopy(artifact)
        invalid["interaction_catalog"]["queries"][0]["success_event_ids"] = ["CEVT-001"]
        result = self.check_temporary(invalid)
        self.assertEqual(result.returncode, 2)
        self.assertIn("success_event_ids", result.stderr)

        invalid = copy.deepcopy(artifact)
        invalid["interaction_catalog"]["commands"] = [
            self.command("CMD-001", "申請結果を確定する", "QEVT-001")
        ]
        result = self.check_temporary(invalid)
        self.assertEqual(result.returncode, 2)
        self.assertIn("success_event_ids", result.stderr)

    def check_temporary(self, artifact: dict) -> subprocess.CompletedProcess[str]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "artifact.json"
        self.write_json(path, artifact)
        return self.call(SCRIPT, "check", "--file", path.resolve())

    def test_fixture_matrix_fixes_success_out_of_scope_and_boundary(self) -> None:
        data = self.load_fixture("cases.json")
        scenarios = data["scenarios"]
        self.assertEqual(
            {scenario["kind"] for scenario in scenarios},
            {"success", "out_of_scope", "boundary"},
        )
        out_of_scope = next(
            scenario
            for scenario in scenarios
            if scenario["kind"] == "out_of_scope"
        )
        self.assertEqual(out_of_scope["expected"]["decision"], "stop_and_route")
        self.assertIsNone(out_of_scope["expected"]["artifact_fixture"])
        boundary = next(
            scenario
            for scenario in scenarios
            if scenario["kind"] == "boundary"
        )
        self.assertEqual(boundary["expected"]["base_classification"], "hypothesis")
        self.assertEqual(boundary["expected"]["changed_classification"], "constraint")
        self.assertNotEqual(
            boundary["base"]["condition"],
            boundary["one_change"]["condition"],
        )
        boundary_artifact = self.load_fixture(
            boundary["expected"]["changed_artifact_fixture"]
        )
        solution = boundary_artifact["solution_inputs"][0]
        self.assertEqual(solution["classification"], "constraint")
        self.assertEqual(solution["linked_id"], "CON-001")
        self.assertNotIn(
            "Redis",
            boundary_artifact["requirements"][0]["statement"],
        )

    def test_hypothesis_cannot_be_promoted_to_requirement(self) -> None:
        artifact = self.load_fixture("success.json")
        artifact["claims"].append(
            {
                "id": "CLM-004",
                "statement": "Redisなら問い合わせを減らせるはず",
                "classification": "hypothesis",
                "source": "担当者の提案",
                "observed_at": "2026-09-14",
                "owner": "担当者",
            }
        )
        artifact["requirements"][0]["claim_ids"] = ["CLM-004"]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "promoted.json"
            self.write_json(path, artifact)
            result = self.call(
                SCRIPT,
                "check",
                "--file",
                path.resolve(),
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("要求へ昇格", result.stderr)

    def test_hypothesis_cannot_be_promoted_to_acceptance_observation(self) -> None:
        artifact = self.load_fixture("success.json")
        artifact["claims"].append(
            {
                "id": "CLM-004",
                "statement": "利用者は一秒なら満足するはず",
                "classification": "hypothesis",
                "source": "担当者の推測",
                "observed_at": "2026-09-14",
                "owner": "担当者",
            }
        )
        observation = artifact["observations"]["success"][0]
        observation["claim_ids"] = ["CLM-004"]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "acceptance.json"
            self.write_json(path, artifact)
            result = self.call(
                SCRIPT,
                "check",
                "--file",
                path.resolve(),
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("確認済み観測へ昇格", result.stderr)

    def test_design_proposal_cannot_link_back_to_constraint_or_requirement(self) -> None:
        artifact = self.load_fixture("boundary.json")
        solution = artifact["solution_inputs"][0]
        solution["classification"] = "design_proposal"
        solution["linked_id"] = "CON-001"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "proposal.json"
            self.write_json(path, artifact)
            result = self.call(
                SCRIPT,
                "check",
                "--file",
                path.resolve(),
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("design proposalが要求へ逆流", result.stderr)

    def test_same_how_becomes_hypothesis_when_decision_changes_to_proposal(self) -> None:
        artifact = self.load_fixture("boundary.json")
        claim = next(item for item in artifact["claims"] if item["id"] == "CLM-004")
        claim["classification"] = "hypothesis"
        claim["source"] = "担当者の未承認提案"
        claim["owner"] = "担当者"
        artifact["constraints"] = []
        artifact["hypotheses"] = [
            {
                "id": "HYP-001",
                "statement": "Redisを使えばセッション継続を実現できる",
                "claim_ids": ["CLM-004"],
                "falsification_method": "後続設計で要求条件を満たす代替案と比較する",
                "affected_ids": ["REQDOC-session-continuity", "REQ-001"],
            }
        ]
        solution = artifact["solution_inputs"][0]
        solution["classification"] = "hypothesis"
        solution["linked_id"] = "HYP-001"
        solution["rationale"] = "決定者と必須性がなく、手段の有効性が未検証である"
        artifact["handoff"]["downstream"]["cloud_design"] = ["REQ-001", "HYP-001"]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "proposal-boundary.json"
            self.write_json(path, artifact)
            result = self.call(
                SCRIPT,
                "check",
                "--file",
                path.resolve(),
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")

    def test_write_refuses_implicit_overwrite_and_requires_next_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repo = base / "repository"
            repo.mkdir()
            source = (FIXTURES / "success.json").resolve()
            first = self.call(
                SCRIPT,
                "write",
                "--repo",
                repo.resolve(),
                "--slug",
                "application-status",
                "--file",
                source,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stderr, "")
            target = (
                repo
                / "system-design/requirements/application-status.requirements.json"
            )
            self.assertEqual(first.stdout.strip(), str(target.resolve()))

            duplicate = self.call(
                SCRIPT,
                "write",
                "--repo",
                repo.resolve(),
                "--slug",
                "application-status",
                "--file",
                source,
            )
            self.assertEqual(duplicate.returncode, 2)
            self.assertIn("--expected-version", duplicate.stderr)

            update = copy.deepcopy(self.load_fixture("success.json"))
            update["artifact"]["version"] = 2
            update["decision_history"].append(
                {
                    "version": 2,
                    "changed_claim_ids": ["CLM-001"],
                    "affected_ids": ["DRV-001"],
                    "summary": "問い合わせ集中の観測を再確認した",
                }
            )
            update_path = base / "update.json"
            self.write_json(update_path, update)
            replaced = self.call(
                SCRIPT,
                "write",
                "--repo",
                repo.resolve(),
                "--slug",
                "application-status",
                "--file",
                update_path.resolve(),
                "--expected-version",
                "1",
            )
            self.assertEqual(replaced.returncode, 0, replaced.stderr)
            self.assertEqual(json.loads(target.read_text())["artifact"]["version"], 2)

    def test_distribution_copy_has_no_source_checkout_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            copied = base / "system-design"
            shutil.copytree(ROOT / "plugins/system-design", copied)
            fixture = base / "artifact.json"
            shutil.copy2(FIXTURES / "success.json", fixture)
            copied_script = (
                copied
                / "skills/discover-requirements/scripts/requirements.py"
            )
            result = self.call(
                copied_script,
                "check",
                "--file",
                fixture.resolve(),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
