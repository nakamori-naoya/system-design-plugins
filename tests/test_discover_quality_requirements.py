#!/usr/bin/env python3
"""discover-quality-requirements の検査script（quality.py）の正例・反例・境界例。

基準資料: write-docの quality-requirements template が定める記法（scriptのdocstringに述語を列挙）。
入力: 標準入力のMarkdown本文と、--upstream の要求発見・利用負荷モデル資料（fixture）。
"""

from __future__ import annotations

import unittest

from canon_case import QUALITY, REQUIREMENTS, SKILLS, WORKLOAD, CanonCase


class QualityContractTest(CanonCase):
    script = SKILLS / "discover-quality-requirements/scripts/quality.py"
    fixture = QUALITY
    arguments = ["--upstream", str(REQUIREMENTS), "--upstream", str(WORKLOAD)]

    def test_success_fixture_passes(self) -> None:
        payload = self.assert_pass(self.body())
        self.assertEqual(payload["document_type"], "quality-requirements")
        self.assertEqual(payload["status"], "unresolved")
        self.assertEqual(payload["quality_requirements"], ["QR-001", "QR-002", "QR-003"])
        self.assertEqual(payload["measurable"], ["QR-001", "QR-002"])
        self.assertEqual(payload["open_conflicts"], ["QCON-001"])

    def test_human_first_format_passes_without_fixed_headings(self) -> None:
        body = """# 申請結果確認の非機能要件

最優先で守る性質は、集中時にも申請者が結果を確認できることである。

## 性能

確認要求の95%を800ミリ秒以内に返す。

## まだ決まっていないこと

最大ピークは実測後に決める。

## 追跡情報

| ID | 守る性質 | 観測・検証 | 根拠と状態 |
|---|---|---|---|
| QR-001 | 集中時にも結果を確認できる | WL-001の負荷で成功率を測る | REQ-001、WL-001、hypothesis |
| QR-OQ-001 | 最大ピーク | 試験導入で測る | WL-OQ-001、open_question |
"""
        payload = self.assert_pass(body)
        self.assertEqual(payload["quality_requirements"], ["QR-001"])
        self.assertEqual(payload["open_questions"], ["QR-OQ-001"])

    def test_upstream_required(self) -> None:
        self.arguments = []
        self.assert_fail(self.body(), "--upstream で上流資料が渡されていません")

    def test_threshold_notation(self) -> None:
        self.assert_fail(self.mutate("| >= 99.9 % |", "| 99.9% |"), "QR-001 の閾値は `<演算子> <数値> <単位>`")
        self.assert_fail(self.mutate("| >= 99.9 % |", "| 高い |"), "QR-001 の閾値は")
        self.assert_fail(self.mutate("| 未決 | 確定日の集中10分間 | 全確認要求 | 集中倍率が決まってから負荷試験で確かめる | open_question |", "| >= 100 件/秒 | 確定日の集中10分間 | 全確認要求 | 集中倍率が決まってから負荷試験で確かめる | open_question |"), "open_question なので閾値は 未決")
        self.assert_fail(self.mutate("| <= 800 ミリ秒 | ピーク10分間 | 全確認要求 | `WL-001` の80件/秒を10分与える負荷試験 | hypothesis |", "| 未決 | ピーク10分間 | 全確認要求 | `WL-001` の80件/秒を10分与える負荷試験 | hypothesis |"), "QR-002 の閾値は")

    def test_category_vocabulary(self) -> None:
        self.assert_fail(self.mutate("| QR-002 | 応答時間 |", "| QR-002 | レイテンシ |"), "QR-002.分類 は")
        self.assert_fail(self.mutate("| QR-001 | 可用性 | 確認経路の外形監視 | 確認要求の成功率 | >= 99.9 % | 確定日の集中10分間 | 全確認要求 | `WL-001` のピークを与える負荷試験と外形監視の集計 | agreed_decision |", "| QR-001 | 可用性 | 確認経路の外形監視 | 確認要求の成功率 | >= 99.9 % | 確定日の集中10分間 | 全確認要求 | `WL-001` のピークを与える負荷試験と外形監視の集計 | fact |"), "QR-001.根拠状態 の根拠状態は")

    def test_coverage_needs_ten_categories(self) -> None:
        self.assert_fail(self.mutate("| 費用 | 未決 | 費用上限は `WL-OQ-001` が決まるまで置かない | なし |\n", ""), "10区分を各1行")
        self.assert_fail(self.mutate("| 可用性 | 指定済み | 集中時間帯に確認できることが業務上の失敗を防ぐ | QR-001 |", "| 可用性 | 指定済み | 集中時間帯に確認できることが業務上の失敗を防ぐ | QR-002 |"), "別の分類の品質要求")
        self.assert_fail(self.mutate("| 可用性 | 指定済み | 集中時間帯に確認できることが業務上の失敗を防ぐ | QR-001 |", "| 可用性 | 未決 | 集中時間帯に確認できるかは `QR-OQ-001` で決める | QR-001 |"), "測定可能な品質要求があるので指定済み")
        self.assert_fail(self.mutate("| 整合性 | 非該当 | 確認は確定済み結果の読み取りだけで、書き込みの競合が無い | なし |", "| 整合性 | 非該当 | 確認は確定済み結果の読み取りだけで、書き込みの競合が無い | QR-001 |"), "非該当なので QR- を持てません")
        self.assert_fail(self.mutate("| 運用性 | 未決 | 少人数運用で扱える障害対応の範囲は `QR-OQ-002` で決める | なし |", "| 運用性 | 未決 | 少人数運用で扱える障害対応の範囲は構成設計で決める | なし |"), "未決なので理由または品質要求IDに決める問い")
        self.assert_fail(self.mutate("| QR-OQ-002 | open_question | 少人数運用で扱える障害対応の範囲 | 運用責任者が構成設計の前に決める | QR-001 |\n", ""), "参照が未解決です: QR-OQ-002")
        self.assert_fail(self.mutate("| WL-OQ-001 | open_question | 確定日の集中倍率は上流で未決のため継続する | 直近2四半期の確認記録を取得する | QCON-001、QR-003 |\n", ""), "引く問い ['WL-OQ-001'] が仮説と未決の open_question 行にありません")

    def test_open_conflict_needs_resolving_question(self) -> None:
        self.assert_fail(self.mutate("| QCON-001、QR-001 |", "| QR-001 |").replace("| QCON-001、QR-003 |", "| QR-003 |"), "open の矛盾が仮説と未決の open_question 行の影響先から参照されていません: ['QCON-001']")
        self.assert_fail(self.mutate("| QCON-001 | QR-001、WL-OQ-001 |", "| QCON-001 | QR-001 |"), "対立するIDは2つ以上")
        self.assert_fail(self.mutate("| 事業責任者と運用責任者 | open |", "| 事業責任者と運用責任者 | pending |"), "QCON-001.状態 は")

    def test_pending_rows(self) -> None:
        self.assert_fail(self.mutate("| QR-HYP-001 | hypothesis |", "| QR-HYP-001 | open_question |"), "IDの種別と一致しません")
        self.assert_fail(self.mutate("| REQ-OQ-002 | open_question | 結果の保持年限は上流で未決のため継続する |", "| REQ-OQ-009 | open_question | 結果の保持年限は上流で未決のため継続する |"), "上流参照が未解決です: REQ-OQ-009")

    def test_trace_covers_all_quality_requirements(self) -> None:
        self.assert_fail(self.mutate("| QR-003 | DRV-001 | WL-001、WL-OQ-001 | 未作成 |\n", ""), "追跡に現れない品質要求があります: ['QR-003']")
        payload = self.assert_pass(self.mutate("| QR-001 | REQ-001、DRV-001 | WL-001 | 未作成 |", "| QR-001 | REQ-001、DRV-001 | WL-001 | ADR-001、NODE-API |"))
        self.assertEqual(payload["status"], "unresolved")

    def test_status_ready_when_nothing_open(self) -> None:
        body = self.body()
        body = body.replace("| QR-003 | 処理量 | 確認経路の入口 | 受理できる確認要求数 | 未決 | 確定日の集中10分間 | 全確認要求 | 集中倍率が決まってから負荷試験で確かめる | open_question |\n", "")
        body = body.replace("| 処理量 | 未決 | 最大負荷は `WL-OQ-001` の集中倍率が決まるまで閾値を置かない | QR-003 |", "| 処理量 | 非該当 | 確認経路の処理量は可用性の成功率で測る | なし |")
        body = body.replace("| 耐久性 | 未決 | 結果の保持年限は `REQ-OQ-002` が決まるまで閾値を置かない | なし |", "| 耐久性 | 非該当 | 結果の一次データは審査システムが持つ | なし |")
        body = body.replace("| 復旧性 | 未決 | 復旧目標は `QR-OQ-001` で事業責任者が判断する | なし |", "| 復旧性 | 非該当 | 復旧は審査システムの手順に従う | なし |")
        body = body.replace("| 運用性 | 未決 | 少人数運用で扱える障害対応の範囲は `QR-OQ-002` で決める | なし |", "| 運用性 | 非該当 | 運用は組織の共通手順に従う | なし |")
        body = body.replace("| 費用 | 未決 | 費用上限は `WL-OQ-001` が決まるまで置かない | なし |", "| 費用 | 非該当 | 費用上限は制約として扱う | なし |")
        body = body.replace("| QCON-001 | QR-001、WL-OQ-001 | `QR-001` は集中10分間の成功率を求める一方、集中倍率が分からず必要容量を比較できない | 事業責任者と運用責任者 | open |", "| なし | なし | なし | なし | なし |")
        head, rest = body.split("## 仮説と未決\n", 1)
        tail = rest.split("## 追跡\n", 1)[1]
        body = head + "## 仮説と未決\n\n| ID | 根拠状態 | 内容 | 検証計画 | 影響先 |\n|---|---|---|---|---|\n| QR-HYP-001 | hypothesis | 確認の95パーセンタイル800ミリ秒なら電話への回帰を抑えられる | 申請者20人の操作と問い合わせを観測する | QR-002 |\n\n## 追跡\n" + tail
        body = body.replace("| QR-003 | DRV-001 | WL-001、WL-OQ-001 | 未作成 |\n", "")
        body = body.replace("確定日の集中倍率（`WL-OQ-001`）と確認経路（`REQ-OQ-001`）は未決なので、負荷試験は始められるが、正式なSLOは確定しない。", "")
        payload = self.assert_pass(body)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["conflicts"], [])


if __name__ == "__main__":
    unittest.main()
