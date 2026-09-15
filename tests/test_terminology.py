#!/usr/bin/env python3
"""Regression tests for shared terminology references."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/system-design/scripts/terminology.py"
REQ = ROOT / "tests/fixtures/discover-requirements/success.json"
WORKLOAD = ROOT / "tests/fixtures/discover-workload-model/success.json"
TERMINOLOGY = ROOT / "tests/fixtures/terminology/success.md"


class TerminologyContractTest(unittest.TestCase):
    def write(self, path: Path, value: object) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def call(self, glossary: Path, *artifacts: Path) -> subprocess.CompletedProcess[str]:
        arguments = ["python3", str(SCRIPT), "check", "--terminology", str(glossary)]
        for artifact in artifacts:
            arguments.extend(("--artifact", str(artifact)))
        return subprocess.run(arguments, text=True, capture_output=True, check=False)

    def seed(self, root: Path) -> tuple[Path, Path, Path]:
        glossary_text = """---
version: 1
subject: 共有用語
---

# 共有するユビキタス言語

## 設計上の概念

### 処理集中

共有資源へ処理が集中する状態。

- 状態: 暫定
- 根拠: 要求確認
- 見直し条件: 観測軸が変わったとき
"""
        glossary_path = root / "glossary.md"
        glossary_path.write_text(glossary_text, encoding="utf-8")
        outputs = []
        for name, source in (("requirements.json", REQ), ("workload.json", WORKLOAD)):
            artifact = json.loads(source.read_text(encoding="utf-8"))
            artifact["terminology"] = {
                "source": {"locator": str(glossary_path), "version": 1},
                "usages": [{"subject_id": artifact["terminology"]["usages"][0]["subject_id"], "preferred_terms": ["処理集中"]}],
            }
            path = root / name
            self.write(path, artifact)
            outputs.append(path)
        return glossary_path, outputs[0], outputs[1]

    def test_multiple_artifacts_reference_one_terminology_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            glossary, requirements, workload = self.seed(Path(temporary))
            result = self.call(glossary, requirements, workload)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_heading_based_fixture_is_accepted(self) -> None:
        text = TERMINOLOGY.read_text(encoding="utf-8")
        self.assertIn("## コマンド", text)
        self.assertIn("## クエリ", text)
        self.assertIn("## コマンドイベント", text)
        self.assertIn("## クエリイベント", text)
        self.assertIn("## 時間イベント", text)
        self.assertIn("## システムイベント", text)
        self.assertIn("## 業務上の概念", text)
        self.assertIn("## 負荷特性", text)
        with tempfile.TemporaryDirectory() as temporary:
            artifact = json.loads(WORKLOAD.read_text(encoding="utf-8"))
            artifact["terminology"] = {
                "source": {"locator": str(TERMINOLOGY), "version": 1},
                "usages": [
                    {"subject_id": "WL-001", "preferred_terms": ["注文受付イベント", "到着率"]}
                ],
            }
            path = Path(temporary) / "workload.json"
            self.write(path, artifact)
            result = self.call(TERMINOLOGY, path)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_version_drift_and_unknown_term_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            glossary, requirements, workload = self.seed(root)
            artifact = json.loads(workload.read_text(encoding="utf-8"))
            artifact["terminology"]["source"]["version"] = 2
            self.write(workload, artifact)
            result = self.call(glossary, requirements, workload)
            self.assertEqual(result.returncode, 2)
            self.assertIn("versionが不一致", result.stderr)

            artifact["terminology"]["source"]["version"] = 1
            artifact["terminology"]["usages"][0]["preferred_terms"] = ["未登録用語"]
            self.write(workload, artifact)
            result = self.call(glossary, requirements, workload)
            self.assertEqual(result.returncode, 2)
            self.assertIn("用語正本にない推奨用語名", result.stderr)

    def test_duplicate_preferred_label_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            glossary, requirements, workload = self.seed(root)
            value = glossary.read_text(encoding="utf-8")
            value += """

### 処理集中

別の定義。

- 状態: 暫定
- 根拠: 別資料
- 見直し条件: 定義が変わったとき
"""
            glossary.write_text(value, encoding="utf-8")
            result = self.call(glossary, requirements, workload)
        self.assertEqual(result.returncode, 2)
        self.assertIn("推奨用語名が重複", result.stderr)

    def test_table_or_unknown_concept_category_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            glossary, requirements, workload = self.seed(root)
            value = glossary.read_text(encoding="utf-8")
            glossary.write_text(value + "\n| 用語 | 定義 |\n|---|---|\n", encoding="utf-8")
            result = self.call(glossary, requirements, workload)
            self.assertEqual(result.returncode, 2)
            self.assertIn("Markdown表ではなく", result.stderr)

            glossary.write_text(value.replace("## 設計上の概念", "## その他"), encoding="utf-8")
            result = self.call(glossary, requirements, workload)
            self.assertEqual(result.returncode, 2)
            self.assertIn("未知の概念種別", result.stderr)

            glossary.write_text(value.replace("## 設計上の概念", "## 業務イベント"), encoding="utf-8")
            result = self.call(glossary, requirements, workload)
            self.assertEqual(result.returncode, 2)
            self.assertIn("未知の概念種別", result.stderr)


if __name__ == "__main__":
    unittest.main()
