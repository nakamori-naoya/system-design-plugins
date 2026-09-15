#!/usr/bin/env python3
"""公開宣言の文書化契約だけを検査する。実モデルの保存試験ではない。"""
import copy
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAYBOOKS = ROOT / "plugins/system-design/playbooks/system-design"
CASES = {
    "discover-requirements": ("requirements-discovery", "requirements_document_path"),
    "discover-workload-model": ("workload-model", "workload_document_path"),
    "discover-quality-requirements": ("quality-requirements", "quality_document_path"),
    "design-cloud-architecture": ("cloud-architecture", "architecture_document_path"),
}


def check_contract(value, identifier):
    document_type, output = CASES[identifier]
    contract = value["contract"]
    assert contract["document_destination"] == {
        "new": ["output_directory"], "update": ["update_target"], "exclusive": True,
    }, f"{identifier}: 保存先の排他宣言"
    assert contract["document"] == {
        "contract": "write-doc/write-doc", "version": 2,
        "new_name": document_type + ".md", "result": ["status", "path", "reason"],
    }, f"{identifier}: 文書化契約ID・版・出力"
    document = next(step for step in value["steps"] if step["id"] == "document")
    assert document["playbook"] == "write-doc", f"{identifier}: 公開入口"
    assert document["input"] == {
        "document_type": document_type,
        "material": [{"kind": "file", "path": "${material}"}],
    }, f"{identifier}: 素材入力・専用型"
    assert set(document["needs"]) == {
        "material", "verification_report", "document_destination",
    }, f"{identifier}: 文書化の必須入力"
    assert document["provides"] == [output], f"{identifier}: 正本パス以外の旧出力"
    assert "when" not in document, f"{identifier}: 未決時の保存を省略"
    assert contract["outcome"]["status"] == "${verification_report.status}", f"{identifier}: 設計状態の保持"
    assert contract["outcome"]["document_path"] == "${" + output + "}", f"{identifier}: 正本パスの対応"
    assert "write_doc_config" not in contract["cleanup"]["delete_after_document"], f"{identifier}: 相手用設定の後片付け"


class DocumentContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values = {}
        for identifier in CASES:
            result = subprocess.run(
                ["yq", "-o=json", ".", str(PLAYBOOKS / identifier / "playbook.yml")],
                check=True, text=True, capture_output=True,
            )
            cls.values[identifier] = json.loads(result.stdout)

    def test_four_public_contracts(self):
        for identifier, value in self.values.items():
            with self.subTest(identifier=identifier):
                check_contract(value, identifier)

    def test_rejects_previous_contract_and_incomplete_binding(self):
        identifier = "discover-requirements"
        for mutation in ("version", "material", "unknown_input", "destination", "old_output", "promoted_status", "update_mode"):
            with self.subTest(mutation=mutation):
                value = copy.deepcopy(self.values[identifier])
                document = next(step for step in value["steps"] if step["id"] == "document")
                if mutation == "version": value["contract"]["document"]["version"] = 1
                elif mutation == "material": document["input"]["material"] = ["${material}"]
                elif mutation == "unknown_input": document["input"]["output_to"] = "/tmp/output.yml"
                elif mutation == "destination": document["needs"].remove("document_destination")
                elif mutation == "old_output": document["provides"].append("write_doc_config")
                elif mutation == "promoted_status": value["contract"]["outcome"]["status"] = "${document.status}"
                else: value["contract"]["document_destination"].pop("update")
                with self.assertRaises(AssertionError): check_contract(value, identifier)


if __name__ == "__main__":
    unittest.main()
