#!/usr/bin/env python3
"""design-cloud-architecture の検査script（architecture.py）の正例・反例・境界例。

正本: write-docの cloud-architecture template が定める記法（scriptのdocstringに述語を列挙）。
入力: 標準入力のMarkdown本文、--provider、--upstream の要求発見・利用負荷・品質要求正本（fixture）。
"""

from __future__ import annotations

import unittest

from canon_case import ARCHITECTURE, QUALITY, REQUIREMENTS, SKILLS, WORKLOAD, CanonCase


class ArchitectureContractTest(CanonCase):
    script = SKILLS / "design-cloud-architecture/scripts/architecture.py"
    fixture = ARCHITECTURE
    arguments = ["--provider", "aws", "--upstream", str(REQUIREMENTS), "--upstream", str(WORKLOAD), "--upstream", str(QUALITY)]

    def test_success_fixture_passes(self) -> None:
        payload = self.assert_pass(self.body())
        self.assertEqual(payload["document_type"], "cloud-architecture")
        self.assertEqual(payload["status"], "unresolved")
        self.assertEqual(payload["provider"], "aws")
        self.assertEqual(payload["provider_constraints"], ["CON-001"])
        self.assertEqual(payload["nodes"], ["NODE-EDGE", "NODE-API", "NODE-DB"])
        self.assertEqual(payload["unresolved_capabilities"], ["バックアップ/DR"])
        self.assertEqual(payload["accepted_adrs"], [])

    def test_provider_is_a_public_input(self) -> None:
        self.arguments = ["--upstream", str(REQUIREMENTS), "--upstream", str(WORKLOAD), "--upstream", str(QUALITY)]
        self.assert_fail(self.body(), "aws または gcp", "--provider", "azure")
        self.assert_fail(self.body(), "入力provider（GCP）と一致しません", "--provider", "gcp")
        result = self.run_check(self.body())
        self.assertEqual(result.returncode, 2)
        self.assertIn("--provider", result.stderr)

    def test_provider_constraint_must_be_agreed(self) -> None:
        self.assert_fail(self.mutate("| CON-001 | agreed_decision |", "| CON-001 | hypothesis |"), "agreed_decision の CON-（入力providerの根拠）がありません")
        self.assert_fail(self.mutate("| プロバイダー | AWS | GCP | CON-001 |", "| プロバイダー | AWS | GCP | REQ-001 |"), "プロバイダー の根拠IDに agreed_decision の CON- がありません")
        self.assert_fail(self.mutate("| 単一プロバイダーへ依存する | agreed_decision |", "| 単一プロバイダーへ依存する | hypothesis |"), "プロバイダー は入力providerの合意なので agreed_decision")

    def test_twelve_capabilities_once(self) -> None:
        self.assert_fail(self.mutate("| デリバリー | GitHub ActionsからECSへのローリング更新 |", "| 配置 | GitHub ActionsからECSへのローリング更新 |"), "代替案比較.選定項目 は")
        self.assert_fail(self.mutate("| ID管理 | 非該当 | Cognito |", "| エッジ | 非該当 | Cognito |"), "12選定項目を各1行")

    def test_selection_state_rules(self) -> None:
        self.assert_fail(self.mutate("| バックアップ/DR | 未決 |", "| バックアップ/DR | 大阪への複製 |"), "open_question なので採用候補は 未決")
        self.assert_fail(self.mutate("| QR-001、ARC-OQ-001 | 該当なし |", "| QR-001 | 該当なし |"), "open_question なので根拠IDに決める問い")
        self.assert_fail(self.mutate("| ID管理 | 非該当 | Cognito | CON-001 | 該当なし | 利用者認証は組織のID基盤へ委ねる | not_applicable |", "| ID管理 | Cognito | なし | CON-001 | 該当なし | 利用者認証は組織のID基盤へ委ねる | not_applicable |"), "not_applicable なので採用候補は 非該当")
        self.assert_fail(self.mutate("| 計算処理 | ECS on Fargate | EKS、Lambda |", "| 計算処理 | ECS on Fargate | なし |"), "比較のため代替案が1つ以上必要")
        self.assert_fail(self.mutate("| ARC-OQ-001 | open_question | リージョン障害時に何時間で復旧すべきか |", "| ARC-OQ-002 | open_question | リージョン障害時に何時間で復旧すべきか |"), "参照が未解決です: ARC-OQ-001")

    def test_nodes_appear_in_diagram_and_trace(self) -> None:
        self.assert_fail(self.mutate('NODE_DB[("NODE-DB<br/>結果データベース")]', 'NODE_DB[("結果データベース")]'), "インフラ構成図に現れない図ノードがあります: ['NODE-DB']")
        self.assert_fail(self.mutate("  subgraph AU_DATA[\"東京リージョン・結果データ\"]\n    NODE_DB[(\"NODE-DB<br/>結果データベース\")]\n  end\n", "  subgraph AU_DATA[\"東京リージョン・結果データ\"]\n    NODE_DB[(\"NODE-DB<br/>結果データベース\")]\n"), "subgraph と end が対応していません")
        self.assert_fail(self.mutate("flowchart LR", "graph LR"), "flowchart で始め")
        self.assert_fail(self.mutate("| ADR-001 | NODE-EDGE、NODE-API、NODE-DB | 80件/秒", "| ADR-001 | NODE-EDGE、NODE-API | 80件/秒"), "要求トレーサビリティに現れない ADR / 図ノードがあります: ['NODE-DB']")
        self.assert_fail(self.mutate("| NODE-DB | 結果データベース。", "| NODE_DB | 結果データベース。"), "図ノードIDの形式が不正です")

    def test_failure_path_origin_is_a_node(self) -> None:
        self.assert_fail(self.mutate("| FAIL-001 | NODE-DB |", "| FAIL-001 | Aurora |"), "FAIL-001 の起点は NODE- でなければなりません")
        self.assert_fail(self.mutate("| FAIL-001 | NODE-DB |", "| FAIL-001 | NODE-CACHE |"), "参照が未解決です: NODE-CACHE")

    def test_adr_state_vocabulary(self) -> None:
        self.assert_fail(self.mutate("失うのはリージョン障害への継続性 | `ARC-OQ-001` が単一リージョンでは満たせない値になったとき | hypothesis |", "失うのはリージョン障害への継続性 | `ARC-OQ-001` が単一リージョンでは満たせない値になったとき | accepted |"), "ADR-001.状態 の根拠状態は")

    def test_upstream_reference_and_missing_upstream(self) -> None:
        self.assert_fail(self.mutate("| REQ-001 | agreed_decision | 申請者が確定した", "| REQ-002 | agreed_decision | 申請者が確定した"), "上流参照が未解決です: REQ-002")
        self.arguments = ["--provider", "aws"]
        self.assert_fail(self.body(), "--upstream で上流正本が渡されていません")

    def test_status_ready_requires_accepted_adr_and_no_open_question(self) -> None:
        body = self.body()
        body = body.replace("| バックアップ/DR | 未決 | 同一リージョン内スナップショット、大阪への複製 | QR-001、ARC-OQ-001 | 該当なし | リージョン障害時の復旧目標が決まるまで方式を選べない | open_question |", "| バックアップ/DR | 同一リージョン内スナップショット | 大阪への複製 | QR-001 | 運用対象を増やさない | リージョン障害には耐えない | hypothesis |")
        body = body.replace("失うのはリージョン障害への継続性 | `ARC-OQ-001` が単一リージョンでは満たせない値になったとき | hypothesis |", "失うのはリージョン障害への継続性 | 復旧目標が単一リージョンでは満たせない値になったとき | agreed_decision |")
        head, rest = body.split("## 仮説と未決\n", 1)
        tail = rest.split("## この資料に書かないもの\n", 1)[1]
        body = head + "## 仮説と未決\n\n| ID | 根拠状態 | 内容 | 設計感度 | 検証計画 | 影響先 |\n|---|---|---|---|---|---|\n| ARC-HYP-001 | hypothesis | 単一リージョン・複数AZで `QR-001` を満たせる | 入口とデータベースの可用性単位 | 障害注入と月額費用を検証する | ADR-001、NODE-EDGE、NODE-DB |\n\n## この資料に書かないもの\n" + tail
        body = body.replace("集中倍率（`WL-OQ-001`）と確認経路（`REQ-OQ-001`）が未決なので、この構成は実装へ渡せる最終決定ではない。設計者と運用責任者は `ADR-001` を承認済みとして実装しない。", "設計者と運用責任者は `ADR-001` を承認済みとして実装へ渡す。")
        body = body.replace("| REQ-OQ-001 | open_question | 確認経路が未決 | エッジ（通知製品を選ばない） |\n", "")
        payload = self.assert_pass(body)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["accepted_adrs"], ["ADR-001"])


if __name__ == "__main__":
    unittest.main()
