#!/usr/bin/env python3
"""検査 script の正例と反例。正例を一時ディレクトリへ写し、壊した写しを拒むことを確かめる。"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins/system-design/skills"
FIXTURES = ROOT / "tests/fixtures"
REQUIREMENTS = SKILLS / "discover-requirements/scripts/check.py"
ARCHITECTURE = SKILLS / "design-cloud-architecture/scripts/architecture.py"


class CheckTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="system-design-check-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        shutil.copytree(FIXTURES, self.root, dirs_exist_ok=True)

    def run_script(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["python3", *arguments], text=True, capture_output=True, check=False)

    def edit(self, name: str, old: str, new: str) -> None:
        path = self.root / name
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def assert_pass(self, *arguments: str) -> None:
        result = self.run_script(*arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["verified"])

    def assert_fail(self, diagnosis: str, *arguments: str) -> None:
        result = self.run_script(*arguments)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn(diagnosis, result.stderr)

    def requirements(self) -> tuple[str, str, str]:
        return (str(REQUIREMENTS), "requirements-discovery", str(self.root / "requirements-discovery.md"))

    def nfr(self) -> tuple[str, str, str]:
        return (str(REQUIREMENTS), "non-functional-requirements", str(self.root / "non-functional-requirements.md"))

    def architecture(self) -> tuple[str, str]:
        return (str(ARCHITECTURE), str(self.root / "cloud-architecture.md"))

    def test_fixtures_pass(self):
        self.assert_pass(*self.requirements())
        self.assert_pass(*self.nfr())
        self.assert_pass(*self.architecture())

    def test_comment_is_ignored(self):
        self.edit("cloud-architecture.md", "\n![構成図", "\n<!-- 執筆指示 -->\n![構成図")
        self.assert_pass(*self.architecture())

    def test_missing_h1(self):
        self.edit("requirements-discovery.md", "# 会議室", "会議室")
        self.assert_fail("H1", *self.requirements())

    def test_missing_opening(self):
        self.edit("requirements-discovery.md", "社員が空いている会議室を一件予約し、予約したことをその場で確かめられるようにする。今回作るのは予約と取り消しで、通知の経路は後で決める。\n", "")
        self.assert_fail("本文が無い", *self.requirements())

    def test_mermaid(self):
        self.edit("requirements-discovery.md", "## 前提にする制約", "```mermaid\nflowchart LR\n  A --> B\n```\n\n## 前提にする制約")
        self.assert_fail("Mermaid", *self.requirements())

    def test_missing_diagram_file(self):
        (self.root / "cloud-architecture.assets/infrastructure.drawio.svg").unlink()
        self.assert_fail("図のファイルが無い", *self.architecture())

    def test_diagram_without_definition(self):
        (self.root / "cloud-architecture.assets/infrastructure.drawio.svg").write_text("<svg/>", encoding="utf-8")
        self.assert_fail("draw.io の定義", *self.architecture())

    def test_diagram_outside_assets(self):
        shutil.copy(self.root / "cloud-architecture.assets/infrastructure.drawio.svg", self.root / "infrastructure.drawio.svg")
        self.edit("cloud-architecture.md", "](cloud-architecture.assets/infrastructure.drawio.svg)", "](infrastructure.drawio.svg)")
        self.assert_fail(".assets/ に無い", *self.architecture())

    def test_architecture_without_leading_diagram(self):
        self.edit("cloud-architecture.md", "](cloud-architecture.assets/infrastructure.drawio.svg)\n", "](cloud-architecture.assets/infrastructure.drawio.svg)\n\n## 構成図\n")
        self.edit("cloud-architecture.md", "\n![構成図", "\n導入の一文。\n\n![構成図")
        self.assert_fail("題名のすぐ下", *self.architecture())

    def test_nfr_without_leading_diagram(self):
        self.edit("non-functional-requirements.md", "![守る順位。重複予約を残さないことが最優先で、予約の速さ、費用、通知の順に譲る](non-functional-requirements.assets/priority.drawio.svg)\n", "")
        self.assert_fail("題名のすぐ下", *self.nfr())

    def test_requirements_need_no_leading_diagram(self):
        self.assert_pass(*self.requirements())

    def test_unknown_type(self):
        self.assert_fail("usage", str(REQUIREMENTS), "workload-model", str(self.root / "requirements-discovery.md"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
