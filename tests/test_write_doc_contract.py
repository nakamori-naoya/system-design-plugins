#!/usr/bin/env python3
"""各公開skillがJSON正本を保存した後、write-docの公開契約へ本文を渡す構造を検査する。

正本: 各公開入口のplaybook.ymlと `プラグイン間依存の規則.md`（外部依存はrequires + playbook:だけ）。
入力: 4入口のplaybook.yml。実モデルもwrite-docも呼ばない。
正規化: yqでYAMLをJSON化し、requiresとstepsのlistを読む。
合格述語: requiresに{plugin: write-doc, marketplace: write-doc}があり、`playbook: write-doc`の工程が
  JSON正本を保存する工程より後にあり、その`input.document_type`が入口ごとの文書型slugと一致し、
  外部packageをskill:/script:で呼ばない。
診断: 違反した入口と項目を示す。
正例: 4入口。反例: requires無し、保存工程より前のwrite-doc、別の文書型、skill:でwrite-docを呼ぶ。
境界例: write-doc工程の`input`は文書型だけを固定し、materialや保存先は実行時の値なのでここでは検査しない。
意味評価: 渡す本文がJSON正本のID・根拠・未決を保っているかはagentが読み戻して判断する。
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
    def test_each_skill_hands_document_text_to_write_doc_after_saving_json(self) -> None:
        for identifier, document_type in DOCUMENT_TYPES.items():
            with self.subTest(identifier=identifier):
                playbook = load_yaml(SKILLS / identifier / "playbook.yml")
                self.assertIn({"plugin": "write-doc", "marketplace": "write-doc"}, playbook["requires"])
                steps = playbook["steps"]
                save_index = next(index for index, step in enumerate(steps) if step["id"] == "validate-and-save-canonical")
                write_doc_steps = [(index, step) for index, step in enumerate(steps) if step.get("playbook") == "write-doc"]
                self.assertEqual(len(write_doc_steps), 1)
                index, step = write_doc_steps[0]
                self.assertGreater(index, save_index)
                self.assertEqual(step["input"], {"document_type": document_type})
                self.assertFalse(any(step.get("skill") == "write-doc" or "write-doc" in str(step.get("script", "")) for step in steps))

    def test_direct_skills_do_not_require_public_routing_layer(self) -> None:
        playbooks = ROOT / "plugins/system-design/playbooks"
        self.assertFalse(playbooks.exists())


if __name__ == "__main__":
    unittest.main()
