#!/usr/bin/env python3
"""4入口の検査scriptを、Markdown fixtureを標準入力で渡して実行するtest基盤。

各testは `tests/fixtures/<入口>/success.md`（正例）を読み、文字列の置換で反例・境界例を作って
scriptへ渡す。fixture fileを書き換えず、一時fileも作らない（scriptは標準入力と上流pathだけを読む）。
"""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins/system-design/skills"
FIXTURES = ROOT / "tests/fixtures"
REQUIREMENTS = FIXTURES / "discover-requirements/success.md"
WORKLOAD = FIXTURES / "discover-workload-model/success.md"
QUALITY = FIXTURES / "discover-quality-requirements/success.md"
ARCHITECTURE = FIXTURES / "design-cloud-architecture/success.md"
TERMINOLOGY = FIXTURES / "terminology/success.md"


class CanonCase(unittest.TestCase):
    script: Path
    fixture: Path
    arguments: list[str] = []

    def run_check(self, body: str, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(self.script), "check", *self.arguments, *extra],
            input=body,
            text=True,
            capture_output=True,
            check=False,
        )

    def body(self) -> str:
        return self.fixture.read_text(encoding="utf-8").replace("<FIXTURES>", str(FIXTURES))

    def mutate(self, old: str, new: str, *, count: int = 1) -> str:
        text = self.body()
        self.assertIn(old, text, f"置換元がfixtureにありません: {old}")
        return text.replace(old, new, count)

    def assert_pass(self, body: str, *extra: str) -> dict:
        result = self.run_check(body, *extra)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertTrue(payload["verified"])
        return payload

    def assert_fail(self, body: str, diagnosis: str, *extra: str) -> None:
        result = self.run_check(body, *extra)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertTrue(result.stderr.startswith("FAIL: "), result.stderr)
        self.assertIn(diagnosis, result.stderr)
        self.assertEqual(result.stdout, "")
