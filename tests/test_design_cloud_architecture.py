#!/usr/bin/env python3
"""design-cloud-architecture の検査script（architecture.py）の正例・反例・境界例。

基準資料: write-docの cloud-architecture template が定める記法（scriptのdocstringに述語を列挙）。
入力: 標準入力のMarkdown本文、--provider、--upstream の要求発見・利用負荷・品質要求資料（fixture）。
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
        self.assertEqual(payload["nodes"], ["NODE-EDGE", "NODE-API", "NODE-DB", "NODE-QUEUE", "NODE-NOTIFY"])
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
        self.assert_fail(self.mutate("| QR-OQ-001、ARC-OQ-001 | 該当なし |", "| QR-001 | 該当なし |"), "open_question なので根拠IDに決める問い")
        self.assert_fail(self.mutate("| ID管理 | 非該当 | Cognito | CON-001 |", "| ID管理 | Cognito | なし | CON-001 |"), "not_applicable なので採用候補は 非該当")
        self.assert_fail(self.mutate("| 計算処理 | ECS on Fargate | EKS、Lambda |", "| 計算処理 | ECS on Fargate | なし |"), "比較のため代替案が1つ以上必要")
        self.assert_fail(self.mutate("| ARC-OQ-001 | `open_question` | リージョン障害時に何時間で復旧すべきか |", "| ARC-OQ-002 | `open_question` | リージョン障害時に何時間で復旧すべきか |"), "参照が未解決です: ARC-OQ-001")

    def test_nodes_appear_in_diagram_and_trace(self) -> None:
        self.assert_fail(self.mutate('NODE_DB[("NODE-DB<br/>予約データベース")]', 'NODE_DB[("予約データベース")]'), "インフラ構成図に現れない図ノードがあります: ['NODE-DB']")
        self.assert_fail(self.mutate("    NODE_QUEUE[\"NODE-QUEUE<br/>通知キュー\"]\n  end\n", "    NODE_QUEUE[\"NODE-QUEUE<br/>通知キュー\"]\n"), "subgraph と end が対応していません")
        self.assert_fail(self.mutate("flowchart LR", "graph LR"), "flowchart で始め")
        self.assert_fail(self.mutate("| ADR-001 | NODE-QUEUE、NODE-NOTIFY |", "| ADR-001 | NODE-NOTIFY |"), "要求トレーサビリティに現れない ADR / 図ノードがあります: ['NODE-QUEUE']")
        self.assert_fail(self.mutate("| NODE-DB | 予約データベース。", "| NODE_DB | 予約データベース。"), "図ノードIDの形式が不正です")

    def test_failure_path_origin_is_a_node(self) -> None:
        self.assert_fail(self.mutate("| FAIL-001 | NODE-NOTIFY |", "| FAIL-001 | SQS |"), "FAIL-001 の起点は NODE- でなければなりません")
        self.assert_fail(self.mutate("| FAIL-001 | NODE-NOTIFY |", "| FAIL-001 | NODE-CACHE |"), "参照が未解決です: NODE-CACHE")

    def test_adr_state_vocabulary(self) -> None:
        self.assert_fail(self.mutate("複数リージョン構成を再検討する | hypothesis |", "複数リージョン構成を再検討する | accepted |"), "ADR-001.状態 の根拠状態は")

    def test_upstream_reference_and_missing_upstream(self) -> None:
        self.assert_fail(self.mutate("| REQ-001 | agreed_decision | 施設管理者が利用枠を公開できる |", "| REQ-009 | agreed_decision | 施設管理者が利用枠を公開できる |"), "上流参照が未解決です: REQ-009")
        self.arguments = ["--provider", "aws"]
        self.assert_fail(self.body(), "--upstream で上流資料が渡されていません")


if __name__ == "__main__":
    unittest.main()
