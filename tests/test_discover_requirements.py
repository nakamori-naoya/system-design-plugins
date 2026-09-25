#!/usr/bin/env python3
"""discover-requirements の検査script（requirements.py）の正例・反例・境界例。

読む目印: write-doc の requirements-discovery 型の template にある「検査が読む目印」（述語は script の docstring）。
入力: 標準入力のMarkdown本文だけ（上流資料を持たない）。正例は write-doc の見本と同じ本文の fixture。
"""

from __future__ import annotations

import unittest

from canon_case import REQUIREMENTS, SKILLS, CanonCase


class RequirementsContractTest(CanonCase):
    script = SKILLS / "discover-requirements/scripts/requirements.py"
    fixture = REQUIREMENTS

    def test_success_fixture_passes_and_reports_ids(self) -> None:
        payload = self.assert_pass(self.body())
        self.assertEqual(payload["document_type"], "requirements-discovery")
        self.assertEqual(payload["status"], "unresolved")
        self.assertEqual(payload["requirements"], ["REQ-001", "REQ-002", "REQ-003", "REQ-004"])
        self.assertEqual(payload["derived_requirements"], ["DRV-001", "DRV-002"])
        self.assertEqual(payload["constraints"], ["CON-001", "CON-002"])
        self.assertEqual(payload["hypotheses"], ["REQ-HYP-001"])
        self.assertEqual(payload["open_questions"], ["REQ-OQ-001", "REQ-OQ-002"])

    def test_empty_stdin_is_rejected(self) -> None:
        self.assert_fail("", "標準入力が空")

    def test_headings_are_free(self) -> None:
        self.assert_pass(self.mutate("## 利用者と権限の範囲", "## 誰が何をできるか"))

    def test_trace_section_is_required(self) -> None:
        # 見出しの文言は読まない。追跡の表は見出し行で見つける
        self.assert_pass(self.mutate("## 追跡情報", "## 対応表"))
        self.assert_fail(self.mutate("| ID | 本文で扱う要求 | 根拠 |", "| ID | 要求 | 根拠 |"), "「ID | 本文で扱う要求 | 根拠」の見出し行を持つ追跡の表がありません")
        body = self.body()
        start = body.index("| ID | 本文で扱う要求 | 根拠 |")
        table = (body[start:] + "\n\n").split("\n\n", 1)[0]
        self.assert_fail(body + "\n\n## 付録\n\n" + table + "\n", "「ID | 本文で扱う要求 | 根拠」の表が 2 個あります")

    def test_requirement_ids_are_closed_and_unique(self) -> None:
        self.assert_fail(self.mutate("| DRV-002 |", "| DRV-2 |"), "REQ- / DRV- / CON- / DEC-")
        self.assert_fail(self.mutate("| DRV-002 |", "| DRV-001 |"), "IDが重複しています: DRV-001")
        self.assert_fail(self.mutate("| CON-002 | 2026年12月末までに単一拠点で運用を始める | 事業責任者との合意 |", "| CON-002 | 2026年12月末までに単一拠点で運用を始める |  |"), "「ID | 本文で扱う要求 | 根拠」の表8行目「根拠」が空です")

    def test_routed_state_matches_id_kind(self) -> None:
        self.assert_fail(self.mutate("| REQ-HYP-001 | hypothesis |", "| REQ-HYP-001 | open_question |"), "REQ-HYP-001 の状態は hypothesis")
        self.assert_fail(self.mutate("| REQ-OQ-002 |", "| QR-OQ-002 |"), "REQ-HYP- / REQ-OQ-")

    def test_status_ready_without_routed_table(self) -> None:
        body = self.body()
        head, tail = body.split("| ID | 状態 | 後続で決める論点 |", 1)
        payload = self.assert_pass(head.rstrip() + "\n")
        self.assertEqual(payload["status"], "ready")


if __name__ == "__main__":
    unittest.main()
