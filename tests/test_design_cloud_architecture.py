#!/usr/bin/env python3
"""design-cloud-architecture の検査script（architecture.py）の正例・反例・境界例。

基準資料: write-doc の公開契約「検査が読む目印」の cloud-architecture（scriptのdocstringに述語を列挙）。
入力: 標準入力のMarkdown本文、--upstream の要求発見・利用負荷・品質要求資料（fixture）。
"""

from __future__ import annotations

import re
import unittest

from canon_case import ARCHITECTURE, QUALITY, REQUIREMENTS, SKILLS, WORKLOAD, CanonCase


class ArchitectureContractTest(CanonCase):
    script = SKILLS / "design-cloud-architecture/scripts/architecture.py"
    fixture = ARCHITECTURE
    arguments = ["--upstream", str(REQUIREMENTS), "--upstream", str(WORKLOAD), "--upstream", str(QUALITY)]

    def test_success_fixture_passes(self) -> None:
        payload = self.assert_pass(self.body())
        self.assertEqual(payload["document_type"], "cloud-architecture")
        self.assertEqual(payload["status"], "unresolved")
        self.assertEqual(payload["provider_constraints"], ["CON-001"])
        self.assertEqual(payload["nodes"], ["NODE-EDGE", "NODE-API", "NODE-DB", "NODE-QUEUE", "NODE-NOTIFY"])
        self.assertEqual(payload["unresolved_elements"], ["NODE-NOTIFY"])
        self.assertEqual(payload["open_questions"], ["ARC-OQ-001", "WL-OQ-001", "REQ-OQ-001", "QR-OQ-001"])
        self.assertEqual(payload["accepted_adrs"], [])
        self.assertNotIn("provider", payload)

    def test_resolved_copy_is_ready(self) -> None:
        body = self.body()
        body = body.replace("CON-001、REQ-002、WL-001、QR-001、QR-OQ-001、hypothesis", "CON-001、REQ-002、WL-001、QR-001、QR-OQ-001、agreed_decision")
        body = re.sub(r"^\| (ARC-OQ-001|WL-OQ-001|REQ-OQ-001|QR-OQ-001) \|.*\n", "", body, flags=re.M)
        body = body.replace("REQ-004、WL-003、REQ-OQ-001、open_question", "REQ-004、WL-003、hypothesis")
        body = re.sub(r"`(REQ-OQ-001|WL-OQ-001|QR-OQ-001|ARC-OQ-001)`", "未決", body)
        body = re.sub(r"(QR-OQ-001|ARC-OQ-001)", "未決", body)
        self.assertEqual(self.assert_pass(body)["status"], "ready")

    def test_headings_are_not_read(self) -> None:
        self.assert_pass(self.mutate("## ADR\n", "## 構成は一つの判断で決めた\n"))
        self.assert_pass(self.mutate("## 追跡の表\n", "## IDの一覧\n"))
        self.assert_pass(self.mutate("## 構成図\n", "## 通知だけが非同期の経路を通る\n"))

    def test_trace_table_is_required_and_single(self) -> None:
        self.assert_fail(self.mutate("| ID | 内容 | 根拠と状態 |", "| ID | 説明 | 根拠と状態 |"), "追跡の表がありません")
        body = self.body()
        start = body.index("| ID | 内容 | 根拠と状態 |")
        table = (body[start:] + "\n\n").split("\n\n", 1)[0]
        self.assert_fail(body + "\n\n## 付録\n\n" + table + "\n", "表が 2 個あります")

    def test_ids_and_states(self) -> None:
        self.assert_fail(self.mutate("| FAIL-002 |", "| FAIL-001 |"), "IDが重複しています: FAIL-001")
        self.assert_fail(self.mutate("| NODE-DB |", "| DB-NODE |"), "追跡の表のIDは")
        self.assert_fail(self.mutate("CON-001、REQ-002、WL-001、QR-001、QR-OQ-001、hypothesis", "CON-001、REQ-002、WL-001、QR-001、QR-OQ-001、open_question"), "ADR-001.根拠と状態")
        self.assert_fail(self.mutate("| ARC-HYP-001 | 単一リージョン・複数AZでQR-OQ-001を満たせる | ADR-001、NODE-DB、hypothesis |", "| ARC-HYP-001 | 単一リージョン・複数AZでQR-OQ-001を満たせる | ADR-001、NODE-DB、open_question |"), "ARC-HYP-001.根拠と状態")
        self.assert_fail(self.mutate("NODE-QUEUE、QR-003、hypothesis", "NODE-QUEUE、QR-003、hypothesis、agreed_decision"), "FAIL-001.根拠と状態")

    def test_citations(self) -> None:
        self.assert_fail(self.mutate("REQ-004、WL-003、QR-003、hypothesis", "hypothesis"), "NODE-QUEUE の根拠と状態は CON- か上流のIDを1つ以上")
        self.assert_fail(self.mutate("NODE-DB、QR-001、hypothesis", "QR-001、hypothesis"), "FAIL-002 の根拠と状態は起点の NODE-")
        self.assert_fail(self.mutate("NODE-DB、QR-001、hypothesis", "NODE-CACHE、QR-001、hypothesis"), "参照が未解決です: NODE-CACHE")

    def test_provider_constraint_must_be_agreed(self) -> None:
        self.assert_fail(self.mutate("プロバイダーはAWS | agreed_decision |", "プロバイダーはAWS | hypothesis |"), "agreed_decision の CON- がありません")

    def test_diagram(self) -> None:
        self.assert_fail(self.mutate('NODE_DB[("NODE-DB<br/>予約データベース")]', 'NODE_DB[("予約データベース")]'), "構成図に現れない NODE- があります: ['NODE-DB']")
        self.assert_fail(self.mutate('    NODE_QUEUE["NODE-QUEUE<br/>通知キュー"]\n', '    NODE_QUEUE["NODE-QUEUE<br/>通知キュー"]\n    NODE_DB_REPLICA["NODE-DB-REPLICA<br/>複製"]\n'), "構成図の NODE- が追跡の表にありません: ['NODE-DB-REPLICA']")
        self.assert_fail(self.mutate("    NODE_QUEUE[\"NODE-QUEUE<br/>通知キュー\"]\n  end\n", "    NODE_QUEUE[\"NODE-QUEUE<br/>通知キュー\"]\n"), "subgraph と end が対応していません")
        self.assert_fail(self.mutate("flowchart LR", "graph LR"), "flowchart で始まる mermaid ブロックが1つ必要です（見つかったブロック: 0）")
        body = self.body()
        start = body.index("```mermaid")
        diagram = body[start:body.index("```\n", start + 3) + 4]
        self.assert_fail(body + "\n" + diagram, "見つかったブロック: 2")

    def test_upstream_reference_and_missing_upstream(self) -> None:
        self.assert_fail(self.mutate("REQ-001、REQ-002、REQ-003、WL-001", "REQ-009、REQ-002、REQ-003、WL-001"), "上流参照が未解決です: REQ-009")
        self.arguments = []
        self.assert_fail(self.body(), "--upstream で上流資料が渡されていません")


if __name__ == "__main__":
    unittest.main()
