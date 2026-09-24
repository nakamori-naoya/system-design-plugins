#!/usr/bin/env python3
"""discover-workload-model の検査script（workload.py）の正例・反例・境界例。

基準資料: write-docの workload-model 型の template と見本（scriptのdocstringに宣言）。
入力: 標準入力のMarkdown本文と、--upstream の要求発見資料（fixture）。正例は write-doc の見本と同じ本文の fixture。
"""

from __future__ import annotations

import unittest

from canon_case import REQUIREMENTS, SKILLS, WORKLOAD, CanonCase


class WorkloadContractTest(CanonCase):
    script = SKILLS / "discover-workload-model/scripts/workload.py"
    fixture = WORKLOAD
    arguments = ["--upstream", str(REQUIREMENTS)]

    def test_success_fixture_passes_and_reports_ids(self) -> None:
        payload = self.assert_pass(self.body())
        self.assertEqual(payload["document_type"], "workload-model")
        self.assertEqual(payload["status"], "unresolved")
        self.assertEqual(payload["design_inputs"], ["DIN-001"])
        self.assertEqual(payload["workload_items"], ["WL-001", "WL-002", "WL-003", "WL-004"])
        self.assertEqual(payload["open_questions"], ["WL-OQ-001"])

    def test_headings_are_free(self) -> None:
        self.assert_pass(self.mutate("## 結論", "## 先に結論"))

    def test_trace_section_is_required(self) -> None:
        self.assert_fail(self.mutate("## 追跡情報", "## 対応"), "追跡情報がありません")

    def test_trace_ids_are_closed(self) -> None:
        self.assert_fail(self.mutate("| WL-004 |", "| LOAD-004 |"), "DIN- / WL- / <接頭辞>-OQ-")

    def test_upstream_reference_must_resolve(self) -> None:
        self.assert_fail(self.mutate("| REQ-001、検索への反映 |", "| REQ-009、検索への反映 |"), "上流参照が未解決です: REQ-009")

    def test_upstream_is_required_when_referenced(self) -> None:
        self.arguments = []
        self.assert_fail(self.body(), "--upstream で上流資料が渡されていません")

    def test_status_ready_without_open_question(self) -> None:
        payload = self.assert_pass(self.mutate("| WL-OQ-001 | 年末繁忙期の倍率 | open_question | 最大容量、可用性、費用 |\n", ""))
        self.assertEqual(payload["status"], "ready")


if __name__ == "__main__":
    unittest.main()
