#!/usr/bin/env python3
"""discover-quality-requirements の検査script（quality.py）の正例・反例・境界例。

基準資料: write-docの quality-requirements 型の template と見本（scriptのdocstringに宣言）。
入力: 標準入力のMarkdown本文と、--upstream の要求発見・利用負荷資料（fixture）。正例は write-doc の見本と同じ本文の fixture。
"""

from __future__ import annotations

import unittest

from canon_case import QUALITY, REQUIREMENTS, SKILLS, WORKLOAD, CanonCase


class QualityContractTest(CanonCase):
    script = SKILLS / "discover-quality-requirements/scripts/quality.py"
    fixture = QUALITY
    arguments = ["--upstream", str(REQUIREMENTS), "--upstream", str(WORKLOAD)]

    def test_success_fixture_passes_and_reports_ids(self) -> None:
        payload = self.assert_pass(self.body())
        self.assertEqual(payload["document_type"], "quality-requirements")
        self.assertEqual(payload["status"], "unresolved")
        self.assertEqual(payload["quality_requirements"], ["QR-001", "QR-002", "QR-003", "QR-004"])
        self.assertEqual(payload["open_questions"], ["QR-OQ-001"])

    def test_headings_are_free(self) -> None:
        self.assert_pass(self.mutate("## 性能", "## 応答の速さ"))

    def test_trace_section_is_required(self) -> None:
        self.assert_fail(self.mutate("## 追跡情報", "## 対応"), "追跡情報がありません")

    def test_state_vocabulary(self) -> None:
        self.assert_fail(self.mutate("| REQ-002、WL-002、agreed_decision |", "| REQ-002、WL-002、fact |"), "QR-001.根拠と状態")
        self.assert_fail(self.mutate("| QR-003 |", "| QCOST-003 |"), "QR-<数字> または QR-OQ-<数字>")

    def test_upstream_reference_must_resolve(self) -> None:
        self.assert_fail(self.mutate("| REQ-001、WL-004、hypothesis |", "| REQ-001、WL-009、hypothesis |"), "上流参照が未解決です: WL-009")

    def test_status_ready_without_open_question(self) -> None:
        payload = self.assert_pass(self.mutate("| QR-OQ-001 | 月間可用性の目標 | 年末繁忙期の扱いと停止損失を確認する | WL-OQ-001、open_question |\n", ""))
        self.assertEqual(payload["status"], "ready")


if __name__ == "__main__":
    unittest.main()
