#!/usr/bin/env python3
"""discover-workload-model の検査script（workload.py）の正例・反例・境界例。

正本: write-docの workload-model template が定める記法（scriptのdocstringに述語を列挙）。
入力: 標準入力のMarkdown本文と、--upstream の要求発見正本（fixture）。
"""

from __future__ import annotations

import unittest

from canon_case import REQUIREMENTS, SKILLS, WORKLOAD, CanonCase


class WorkloadContractTest(CanonCase):
    script = SKILLS / "discover-workload-model/scripts/workload.py"
    fixture = WORKLOAD
    arguments = ["--upstream", str(REQUIREMENTS)]

    def test_success_fixture_passes(self) -> None:
        payload = self.assert_pass(self.body())
        self.assertEqual(payload["document_type"], "workload-model")
        self.assertEqual(payload["status"], "unresolved")
        self.assertEqual(payload["design_inputs"], ["DIN-001", "DIN-002"])
        self.assertEqual(payload["workload_items"], ["WL-001", "WL-002"])
        self.assertEqual(payload["open_questions"], ["WL-OQ-001", "REQ-OQ-001"])

    def test_human_first_format_passes_without_fixed_headings(self) -> None:
        body = """# 申請結果確認の利用規模と負荷モデル

初期設計では確認要求80件/秒を1分ピークとして扱う。

## 結論

月20万件、平均2件/秒、1分ピーク80件/秒と仮定する。

## まだ決まっていないこと

確定日の集中倍率は実測後に決める。

## 追跡情報

| ID | 設計入力 | 根拠と状態 | 影響する要求・判断 |
|---|---|---|---|
| DIN-001 | 月間活動時間10万秒 | 推定、hypothesis | REQ-001 |
| WL-001 | 確認80件/秒 | 推定、hypothesis | REQ-001、DRV-001 |
| WL-OQ-001 | 集中倍率 | open_question | 最大容量 |
"""
        payload = self.assert_pass(body)
        self.assertEqual(payload["design_inputs"], ["DIN-001"])
        self.assertEqual(payload["workload_items"], ["WL-001"])
        self.assertEqual(payload["open_questions"], ["WL-OQ-001"])

    def test_upstream_is_required_for_upstream_references(self) -> None:
        self.arguments = []
        self.assert_fail(self.body(), "--upstream で上流正本が渡されていません")
        self.assert_fail(self.body(), "絶対path", "--upstream", "relative.md")
        self.assert_fail(self.body(), "regular file", "--upstream", "/nonexistent/requirements.md")

    def test_unknown_upstream_reference_is_rejected(self) -> None:
        self.assert_fail(self.mutate("要件への影響: `REQ-001` と `DRV-001` の負荷", "要件への影響: `REQ-009` と `DRV-001` の負荷"), "上流参照が未解決です: REQ-009")

    def test_design_input_label_vocabulary(self) -> None:
        self.assert_fail(self.mutate("根拠: 推定。各計算を", "根拠: 感覚。各計算を"), "根拠は ['公開情報', '実測', '利用者決定', '推定'] のどれか")
        self.assert_fail(self.mutate("適用範囲: 初期実装の合格値。\n要件への影響: `REQ-001` と `DRV-001`", "適用範囲: 参考値。\n要件への影響: `REQ-001` と `DRV-001`"), "適用範囲は")
        self.assert_fail(self.mutate("構成への影響: 容量の判断に使う。", "構成への影響: 後で決める。"), "構成への影響は")
        self.assert_fail(self.mutate("根拠: 利用者決定（`SRC-001` の申請件数）と推定（確認回数の想定）。", "根拠: 利用者決定（申請件数）と推定（確認回数の想定）。"), "出典の SRC- がありません")

    def test_estimated_input_needs_calculation_row(self) -> None:
        self.assert_fail(self.mutate("| DIN-001 | 月間の活動時間 | 推定 | 25営業日×4,000秒=100,000秒 | 月 | 中。営業時間帯に偏る想定 | 試験導入の計測 |\n", ""), "推定を根拠にした設計入力が計算に現れません: ['DIN-001']")

    def test_every_design_input_is_connected(self) -> None:
        self.assert_fail(self.mutate("| DIN-001 | REQ-001、DRV-001 | 容量 | hypothesis |\n", ""), "接続に現れない設計入力があります: ['DIN-001']")

    def test_rates_need_numbers_with_units(self) -> None:
        self.assert_fail(self.mutate("| 2件/秒 | 80件/秒 |", "| 多い | 80件/秒 |"), "WL-001.平均率 は `<数値><単位>`")
        self.assert_fail(self.mutate("| 2件/秒 | 80件/秒 |", "| 2 | 80件/秒 |"), "WL-001.平均率 は `<数値><単位>`")
        payload = self.assert_pass(self.mutate("| 2件/秒 | 80件/秒 |", "| 非該当 | 非該当 |"))
        self.assertEqual(payload["workload_items"], ["WL-001", "WL-002"])

    def test_scale_rows_need_state_and_source(self) -> None:
        self.assert_fail(self.mutate("| hypothesis、SRC-001 |", "| SRC-001 |"), "WL-001.根拠状態・根拠ID の根拠状態は")
        self.assert_fail(self.mutate("| hypothesis、SRC-001 |", "| hypothesis |"), "WL-001 の根拠状態・根拠IDに SRC- がありません")
        self.assert_fail(self.mutate("| hypothesis、SRC-001 |", "| hypothesis、SRC-009 |"), "参照が未解決です: SRC-009")

    def test_every_workload_item_has_retention_row(self) -> None:
        self.assert_fail(self.mutate("| WL-002 | 結果1件4KB |", "| WL-001 | 結果1件4KB |"), "データ量・保持・増加に現れない負荷項目があります: ['WL-002']")

    def test_skew_tables_accept_none_row(self) -> None:
        payload = self.assert_pass(self.body())
        self.assertEqual(payload["status"], "unresolved")
        self.assert_fail(self.mutate("| WL-001 | 確定直後の結果確認 |", "| WL-009 | 確定直後の結果確認 |"), "参照が未解決です: WL-009")
        self.assert_fail(self.mutate("### 影響範囲型", "### 増幅型"), "`### 影響範囲型` が1つ必要")

    def test_calculation_vocabulary(self) -> None:
        self.assert_fail(self.mutate("| 月 | 中。営業時間帯に偏る想定 |", "| 月 | ふつう |"), "確度は 高 / 中 / 低")
        self.assert_fail(self.mutate("| DIN-002 | 確認の平均率 | 推定 |", "| DIN-002 | 確認の平均率 | 経験 |"), "根拠種別は")

    def test_pending_rows(self) -> None:
        self.assert_fail(self.mutate("| WL-OQ-001 | open_question |", "| WL-OQ-001 | hypothesis |"), "IDの種別と一致しません")
        self.assert_fail(self.mutate("| REQ-OQ-001 | open_question | 確認経路は上流で未決のため継続する |", "| REQ-OQ-009 | open_question | 確認経路は上流で未決のため継続する |"), "上流参照が未解決です: REQ-OQ-009")
        self.assert_fail(self.mutate("| WL-HYP-001 | hypothesis | 確認ピークは80件/秒である | 試験導入で確認要求の時刻を4週間記録し、1分窓の最大件数を集計する |", "| WL-HYP-001 | hypothesis | 確認ピークは80件/秒である | なし |"), "検証計画が空")

    def test_status_ready_without_open_questions(self) -> None:
        body = self.mutate("| WL-OQ-001 | open_question | 確定日の集中倍率は平常の何倍か | 直近2四半期の確定日の確認記録を取得する | WL-001、DIN-002 |\n", "")
        body = body.replace("| REQ-OQ-001 | open_question | 確認経路は上流で未決のため継続する | 事業責任者の決定を要求発見正本へ戻す | WL-001 |\n", "")
        body = body.replace("確定日の集中倍率（`WL-OQ-001`）と確認経路（`REQ-OQ-001`）が決まるまで、", "")
        payload = self.assert_pass(body)
        self.assertEqual(payload["status"], "ready")


if __name__ == "__main__":
    unittest.main()
