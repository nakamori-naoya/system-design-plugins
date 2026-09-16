#!/usr/bin/env python3
"""discover-requirements の検査script（requirements.py）の正例・反例・境界例。

正本: write-docの requirements-discovery template が定める記法（scriptのdocstringに述語を列挙）。
入力: 標準入力のMarkdown本文だけ（上流正本を持たない）。
"""

from __future__ import annotations

import unittest

from canon_case import FIXTURES, REQUIREMENTS, SKILLS, CanonCase


class RequirementsContractTest(CanonCase):
    script = SKILLS / "discover-requirements/scripts/requirements.py"
    fixture = REQUIREMENTS

    def test_success_fixture_passes_and_reports_status(self) -> None:
        payload = self.assert_pass(self.body())
        self.assertEqual(payload["document_type"], "requirements-discovery")
        self.assertEqual(payload["status"], "unresolved")
        self.assertEqual(payload["requirements"], ["REQ-001"])
        self.assertEqual(payload["derived_requirements"], ["DRV-001"])
        self.assertEqual(payload["constraints"], ["CON-001"])
        self.assertEqual(payload["open_questions"], ["REQ-OQ-001", "REQ-OQ-002"])
        self.assertEqual(payload["hypotheses"], ["REQ-HYP-001"])

    def test_empty_stdin_is_rejected(self) -> None:
        self.assert_fail("", "標準入力が空")

    def test_section_order_and_names_are_fixed(self) -> None:
        self.assert_fail(self.mutate("## 固定制約", "## 制約"), "H2見出しがtemplateの名前と順序に一致しません")
        body = self.body()
        head, tail = body.split("## 用語\n", 1)
        terms, rest = tail.split("## 根拠\n", 1)
        self.assert_fail(head + "## 根拠\n" + rest.split("## 後続設計で決める論点\n", 1)[0] + "## 用語\n" + terms + "## 後続設計で決める論点\n" + rest.split("## 後続設計で決める論点\n", 1)[1], "順序に一致しません")

    def test_intro_must_be_a_paragraph(self) -> None:
        self.assert_fail(self.mutate("**この正本は", "> **この正本は"), "冒頭は本文段落で始める")

    def test_hypothesis_evidence_cannot_become_requirement(self) -> None:
        self.assert_fail(
            self.mutate("根拠: `SRC-001`（`fact`）、`SRC-002`（`agreed_decision`）。", "根拠: `SRC-003`（`hypothesis`）。"),
            "hypothesis の根拠だけで要求",
        )

    def test_requirement_needs_all_label_lines(self) -> None:
        self.assert_fail(self.mutate("検証方法: 対象申請の受入観察", "確認: 対象申請の受入観察"), "REQ-001 にラベル行がありません: ['検証方法']")

    def test_derived_requirement_needs_evidence_in_characteristic(self) -> None:
        self.assert_fail(self.mutate("（`SRC-003`、`hypothesis`）ため", "ため"), "DRV-001 の特性に根拠ID")

    def test_design_decision_needs_agreement_or_derived_requirement(self) -> None:
        self.assert_fail(self.mutate("（`SRC-002`、`agreed_decision`）。だから", "（`SRC-001`、`fact`）。だから"), "DEC-001 に agreed_decision の根拠")

    def test_unconfirmed_evidence_cannot_become_constraint(self) -> None:
        self.assert_fail(self.mutate("| CON-001 | 利用者認証は組織の既存ID基盤へ委ねる | SRC-002、agreed_decision |", "| CON-001 | 利用者認証は組織の既存ID基盤へ委ねる | SRC-003、hypothesis |"), "根拠状態は")
        self.assert_fail(self.mutate("| CON-001 | 利用者認証は組織の既存ID基盤へ委ねる | SRC-002、agreed_decision |", "| CON-001 | 利用者認証は組織の既存ID基盤へ委ねる | SRC-003、agreed_decision |"), "未確認の根拠 SRC-003 を制約へ昇格")

    def test_unknown_reference_is_rejected(self) -> None:
        self.assert_fail(self.mutate("| REQ-HYP-001 | hypothesis | 結果確定は締切日に一括で行われる（`SRC-003`） | 負荷 | DRV-001 |", "| REQ-HYP-001 | hypothesis | 結果確定は締切日に一括で行われる（`SRC-003`） | 負荷 | DRV-002 |"), "参照が未解決です: DRV-002")

    def test_duplicate_id_is_rejected(self) -> None:
        self.assert_fail(self.mutate("### DRV-001:", "### REQ-001:"), "IDが重複しています: REQ-001")

    def test_scope_needs_four_kinds_once(self) -> None:
        self.assert_fail(self.mutate("| 設計説明のみ | 結果確定の通知経路 |", "| 対象外 | 結果確定の通知経路 |"), "スコープの区分は")

    def test_command_event_kind_and_counterpart(self) -> None:
        self.assert_fail(self.mutate("| 申請結果を確認する | クエリ | 申請結果が確認された | クエリ |", "| 申請結果を確認する | クエリ | 申請結果が確認された | コマンド |"), "クエリなのでイベント種別は")
        self.assert_fail(self.mutate("| 申請結果の確定を取り消す | コマンド | 申請結果の確定が取り消された | コマンド | 申請結果を確定する |", "| 申請結果の確定を取り消す | コマンド | 申請結果の確定が取り消された | コマンド | なし |"), "相互参照されていません")
        self.assert_fail(self.mutate("| 保持期限に到達する | — | 申請結果が通常経路の対象外になった | 時間 | なし | 対象内 |", "| 保持期限に到達する | — | 申請結果が通常経路の対象外になった | 時間 | なし | 検討中 |"), "対象 は")

    def test_open_question_state_matches_id_prefix(self) -> None:
        self.assert_fail(self.mutate("| REQ-OQ-002 | open_question |", "| REQ-OQ-002 | hypothesis |"), "ID接頭辞 REQ-HYP- と一致しません")
        self.assert_fail(self.mutate("| REQ-OQ-002 | open_question | 申請結果の物理的な保持年限 | データモデル | REQ-001 | 法務確認の結果で決める |", "| REQ-OQ-002 | open_question | 申請結果の物理的な保持年限 | データモデル | REQ-001 | なし |"), "検証計画が空")

    def test_all_requirements_must_be_observable(self) -> None:
        self.assert_fail(self.mutate("| DRV-001 | 確定直後の集中時間帯に確認できなかった申請者がいない | 申請者と問い合わせ担当・確認記録 |\n", ""), "観測可能な完了に現れない要件があります: ['DRV-001']")

    def test_status_ready_when_no_open_question(self) -> None:
        body = self.mutate("| REQ-OQ-001 | open_question | 確認経路は既存の申請画面か通知か | 品質・構成 | REQ-001 | 事業責任者が2026年9月30日までに決める。推奨は既存の申請画面（認証基盤を共有できるため） |\n", "")
        body = body.replace("| REQ-OQ-002 | open_question | 申請結果の物理的な保持年限 | データモデル | REQ-001 | 法務確認の結果で決める |\n", "")
        body = body.replace("確認経路の優先順位（`REQ-OQ-001`）は未決だが、", "").replace("物理的な保持年限は未決（`REQ-OQ-002`）。", "物理的な保持年限は法務確認済みの7年とする（`SRC-002`）。")
        payload = self.assert_pass(body)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["open_questions"], [])

    def test_terminology_absent_is_a_boundary_case(self) -> None:
        body = self.mutate(
            "用語正本: " + str(FIXTURES / "terminology/success.md") + " 版: 1\n推奨用語名: 申請結果を確定する、申請結果の確定を取り消す、申請結果を確認する、申請者",
            "用語正本: なし",
        )
        payload = self.assert_pass(body)
        self.assertIsNone(payload["terminology"])
        self.assert_fail(self.mutate(" 版: 1\n", "\n"), "版: <整数>")


if __name__ == "__main__":
    unittest.main()
