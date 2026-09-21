#!/usr/bin/env python3
"""各公開skillが grill で問い、検査scriptを標準入力で通し、write-docの公開契約へ本文を渡す構造を検査する。

基準資料: 各公開入口のplaybook.ymlと `プラグイン間依存の規則.md`（外部依存はrequires + playbook:だけ）。
入力: 4入口のplaybook.yml。実モデルもgrillもwrite-docも呼ばない。
正規化: yqでYAMLをJSON化し、requiresとstepsのlistを読む。
合格述語: requiresに{plugin: grill, marketplace: grill}と{plugin: write-doc, marketplace: write-doc}があり、
  `playbook: grill`の工程が `verify`（入口のscripts/配下の検査script）より前に、`playbook: write-doc`の工程が
  `verify` より後にあり、write-docの`input.document_type`が入口ごとの文書型slugと一致し、
  公開入力に `references` があり、外部packageをskill:/script:で呼ばず、JSON資料を保存する工程が無い。
診断: 違反した入口と項目を示す。
正例: 4入口。反例: requires無し、verifyより前のwrite-doc、別の文書型、skill:でwrite-docを呼ぶ、JSON保存工程の残存。
境界例: write-doc工程の`input`は文書型だけを固定し、materialや保存先は実行時の値なのでここでは検査しない。
意味評価: 渡す本文が検査済み本文と同じID・根拠・未決を保っているかはagentが読み戻して判断する。
"""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins/system-design/skills"
DOCUMENT_TYPES = {
    "discover-requirements": "requirements-discovery",
    "discover-workload-model": "workload-model",
    "discover-quality-requirements": "quality-requirements",
    "design-cloud-architecture": "cloud-architecture",
}


def load_yaml(path: Path) -> dict:
    result = subprocess.run(
        ["yq", "-o=json", "-I=0", ".", str(path)],
        text=True, capture_output=True, check=True,
    )
    return json.loads(result.stdout)


class WriteDocHandoffContract(unittest.TestCase):
    def test_each_skill_settles_with_grill_verifies_by_script_then_hands_text_to_write_doc(self) -> None:
        for identifier, document_type in DOCUMENT_TYPES.items():
            with self.subTest(identifier=identifier):
                playbook = load_yaml(SKILLS / identifier / "playbook.yml")
                self.assertIn({"plugin": "write-doc", "marketplace": "write-doc"}, playbook["requires"])
                self.assertIn({"plugin": "grill", "marketplace": "grill"}, playbook["requires"])
                self.assertIn("references", playbook["inputs"])
                steps = playbook["steps"]
                ids = [step["id"] for step in steps]
                self.assertNotIn("validate-and-save-canonical", ids)
                self.assertNotIn("confirm-question-inventory", ids)
                verify_index = next(index for index, step in enumerate(steps) if step["id"] == "verify")
                self.assertTrue(steps[verify_index]["script"].startswith("scripts/"))
                grill_steps = [index for index, step in enumerate(steps) if step.get("playbook") == "grill"]
                self.assertEqual(len(grill_steps), 1)
                self.assertLess(grill_steps[0], verify_index)
                write_doc_steps = [(index, step) for index, step in enumerate(steps) if step.get("playbook") == "write-doc"]
                self.assertEqual(len(write_doc_steps), 1)
                index, step = write_doc_steps[0]
                self.assertGreater(index, verify_index)
                self.assertEqual(step["input"], {"document_type": document_type})
                self.assertIn("verification_result", step["needs"])
                self.assertFalse(any(step.get("skill") in ("write-doc", "grill") or "write-doc" in str(step.get("script", "")) for step in steps))

    def test_direct_skills_do_not_require_public_routing_layer(self) -> None:
        playbooks = ROOT / "plugins/system-design/playbooks"
        self.assertFalse(playbooks.exists())


if __name__ == "__main__":
    unittest.main()
