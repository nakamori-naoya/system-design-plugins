#!/usr/bin/env python3
"""package共有の terminology.py（用語定義と、それを参照するMarkdown資料の整合）の正例・反例・境界例。

基準資料: 用語定義fixture（tests/fixtures/terminology/success.md）と、要求発見fixtureの `## 用語` / `## コマンドとクエリ`。
入力: --terminology の用語定義と --artifact の基準資料Markdown。fixture fileは書き換えず、変種は一時directoryへ置く。
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from canon_case import REQUIREMENTS, ROOT, TERMINOLOGY

SCRIPT = ROOT / "plugins/system-design/scripts/terminology.py"


class TerminologyContractTest(unittest.TestCase):
    def call(self, glossary: Path, *artifacts: Path) -> subprocess.CompletedProcess[str]:
        arguments = ["python3", str(SCRIPT), "check", "--terminology", str(glossary)]
        for artifact in artifacts:
            arguments.extend(("--artifact", str(artifact)))
        return subprocess.run(arguments, text=True, capture_output=True, check=False)

    def artifact_with(self, root: Path, glossary: Path, *, replace: tuple[str, str] | None = None) -> Path:
        text = REQUIREMENTS.read_text(encoding="utf-8").replace("<FIXTURES>/terminology/success.md", str(glossary))
        if replace is not None:
            self.assertIn(replace[0], text)
            text = text.replace(*replace)
        path = root / "requirements.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_fixture_artifact_references_fixture_terminology(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = self.artifact_with(Path(directory), TERMINOLOGY)
            result = self.call(TERMINOLOGY, artifact)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(TERMINOLOGY.resolve()))

    def test_heading_based_glossary_has_all_concept_categories(self) -> None:
        text = TERMINOLOGY.read_text(encoding="utf-8")
        for heading in ("## アクター", "## コマンド", "## クエリ", "## コマンドイベント", "## クエリイベント", "## 時間イベント", "## システムイベント", "## 業務上の概念", "## 負荷特性"):
            self.assertIn(heading, text)

    def test_version_drift_unknown_term_and_missing_section_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            glossary = root / "glossary.md"
            glossary.write_text(TERMINOLOGY.read_text(encoding="utf-8"), encoding="utf-8")
            artifact = self.artifact_with(root, glossary, replace=(" 版: 1\n", " 版: 2\n"))
            result = self.call(glossary, artifact)
            self.assertEqual(result.returncode, 2)
            self.assertIn("versionが不一致", result.stderr)

            artifact = self.artifact_with(root, glossary, replace=("推奨用語名: 申請結果を確定する", "推奨用語名: 未登録用語、申請結果を確定する"))
            result = self.call(glossary, artifact)
            self.assertEqual(result.returncode, 2)
            self.assertIn("用語定義にない推奨用語名", result.stderr)

            artifact = self.artifact_with(root, glossary, replace=(f"用語定義: {glossary} 版: 1", "用語定義: なし"))
            result = self.call(glossary, artifact)
            self.assertEqual(result.returncode, 2)
            self.assertIn("用語定義を参照していません", result.stderr)

            artifact = self.artifact_with(root, glossary, replace=(f"用語定義: {glossary} 版: 1", f"用語定義: {root / 'other.md'} 版: 1"))
            result = self.call(glossary, artifact)
            self.assertEqual(result.returncode, 2)
            self.assertIn("locatorが不一致", result.stderr)

    def test_operation_names_must_match_glossary_category(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            glossary = root / "glossary.md"
            glossary.write_text(TERMINOLOGY.read_text(encoding="utf-8"), encoding="utf-8")
            artifact = self.artifact_with(root, glossary, replace=("| 申請結果を確認する | クエリ |", "| 申請結果を照会する | クエリ |"))
            result = self.call(glossary, artifact)
            self.assertEqual(result.returncode, 2)
            self.assertIn("用語定義にない操作名", result.stderr)

            artifact = self.artifact_with(root, glossary, replace=("| 申請結果を確認する | クエリ | 申請結果が確認された | クエリ |", "| 申請結果を確認する | コマンド | 申請結果が確認された | コマンド |"))
            result = self.call(glossary, artifact)
            self.assertEqual(result.returncode, 2)
            self.assertIn("概念種別が用語定義と一致しません", result.stderr)

    def test_duplicate_preferred_label_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            glossary = root / "glossary.md"
            glossary.write_text(TERMINOLOGY.read_text(encoding="utf-8") + "\n### 申請者\n\n別の定義。\n\n- 状態: 暫定\n- 根拠: 別資料\n- 見直し条件: 定義が変わったとき\n", encoding="utf-8")
            result = self.call(glossary, self.artifact_with(root, glossary))
        self.assertEqual(result.returncode, 2)
        self.assertIn("推奨用語名が重複", result.stderr)

    def test_table_or_unknown_concept_category_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            glossary = root / "glossary.md"
            value = TERMINOLOGY.read_text(encoding="utf-8")
            glossary.write_text(value + "\n| 用語 | 定義 |\n|---|---|\n", encoding="utf-8")
            result = self.call(glossary, self.artifact_with(root, glossary))
            self.assertEqual(result.returncode, 2)
            self.assertIn("Markdown表ではなく", result.stderr)

            glossary.write_text(value.replace("## 設計上の概念", "## その他"), encoding="utf-8")
            result = self.call(glossary, self.artifact_with(root, glossary))
            self.assertEqual(result.returncode, 2)
            self.assertIn("未知の概念種別", result.stderr)


if __name__ == "__main__":
    unittest.main()
