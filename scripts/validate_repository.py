#!/usr/bin/env python3
"""system-design の各公開入口が、自分の references へ届き、兄弟の入口の中身へ依存しないことを検査する。

manifest と配置の一致は harness-tools/tools/validate-plugin-repository.py が見るので、ここでは見ない。

入力: 引数の repository の絶対path。公開入口は plugins/system-design/skills/ 直下の directory。
合格述語: 各入口の SKILL.md が、自分の references/ にある全 .md へ `[..](references/<名前>.md)` の形で直接リンクする。
  SKILL.md は兄弟の入口の directory を含む path（`skills/<兄弟>/`、`../<兄弟>/`、`<兄弟>/references/`、`<兄弟>/scripts/`）を書かない。
失敗時の診断: `FAIL: <理由>` を1行。終了code 1。
正例: この repository そのもの。兄弟や外部の入口の名前を backtick で挙げるだけの文（「`design-cloud-architecture` が決める」）。
反例: self-test の、reference へのリンクの欠落と、兄弟の path への参照。
意味評価として残す範囲: 名前を挙げた文が兄弟への依存を作っていないか、文章の良し悪し。
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

LINK = re.compile(r"\[[^\]]+\]\((references/[^)#]+\.md)(?:#[^)]*)?\)")


class ValidationError(ValueError):
    pass


def validate_repository(repository: Path) -> None:
    skills = repository / "plugins/system-design/skills"
    entries = sorted(path.name for path in skills.iterdir() if path.is_dir())
    for identifier in entries:
        root = skills / identifier
        text = (root / "SKILL.md").read_text(encoding="utf-8")
        linked = {root / link for link in LINK.findall(text)}
        references = set((root / "references").glob("*.md"))
        if linked != references:
            raise ValidationError(f"{identifier} の SKILL.md から全 reference へ直接リンクしていない")
        for sibling in set(entries) - {identifier}:
            name = re.escape(sibling)
            if re.search(rf"(?:skills/|\.\./){name}/|(?<![A-Za-z0-9_-]){name}/(?:references|scripts)/", text):
                raise ValidationError(f"{identifier} の SKILL.md が兄弟の入口の path を書いている: {sibling}")
    print(f"Repository: passed ({len(entries)} entries)")


def self_test(repository: Path) -> None:
    def mutated(label: str, change, needle: str | None) -> None:
        with tempfile.TemporaryDirectory(prefix="system-design-validator-") as value:
            candidate = Path(value) / "repository"
            shutil.copytree(repository, candidate, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            path = candidate / "plugins/system-design/skills/discover-requirements/SKILL.md"
            path.write_text(change(path.read_text(encoding="utf-8")), encoding="utf-8")
            try:
                validate_repository(candidate)
            except ValidationError as exc:
                if needle is None or needle not in str(exc):
                    raise ValidationError(f"「{label}」が期待と違う理由で失敗した: {exc}") from exc
                print(f"Negative: passed ({label})")
                return
            if needle is not None:
                raise ValidationError(f"「{label}」を拒否できない")
            print(f"Positive: passed ({label})")

    mutated("入口名を挙げるだけの文", lambda text: text + "\n構成は `design-cloud-architecture` が決める。\n", None)
    mutated("兄弟の入口の path", lambda text: text + "\n詳しくは ../design-cloud-architecture/references/ を読む。\n", "兄弟の入口の path")
    mutated("reference へのリンクの欠落", lambda text: text.replace("](references/workload-model.md)", "]"), "全 reference へ直接リンクしていない")
    print("Validator self-test: passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    repository = args.repository.resolve()
    validate_repository(repository)
    if args.self_test:
        self_test(repository)


if __name__ == "__main__":
    try:
        main()
    except (ValidationError, OSError, UnicodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
