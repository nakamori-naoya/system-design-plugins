#!/usr/bin/env python3
"""用語定義（見出し形式のMarkdown）と、それを参照する基準資料（Markdown）の整合を検査する。

  python3 terminology.py check --terminology <用語定義の絶対path> --artifact <基準資料Markdownの絶対path> [--artifact ...]

用語定義は frontmatter（version / subject）と、概念種別の H2 見出しの下に `### 推奨用語名` を置く形である。
参照側の基準資料は `## 用語` 節に `用語定義: <絶対path> 版: <整数>` と `推奨用語名: <名>、<名>` を持つ。
通ったときに言えるのは次だけである。

  - 用語定義が表を使わず、既知の概念種別見出しの下に重複しない推奨用語名を置き、各用語が定義・状態・根拠・見直し条件を持つ
  - 各参照側基準資料の `## 用語` が同じ用語定義（path）と同じ版を指し、列挙した推奨用語名がすべて用語定義にある
  - 参照側基準資料に `## コマンドとクエリ` の表があれば、種別が コマンド / クエリ の操作名が用語定義の同じ概念種別（コマンド / クエリ）の推奨用語名である

exit 0 = 通った（stdoutに用語定義の絶対path） / 2 = 述語が成り立たない（診断は標準エラー `FAIL: <理由>`）。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canon import Document, strip_markup, tables, terminology_lines  # noqa: E402  package共有の構文解析


CATEGORIES = {
    "アクター",
    "コマンド",
    "クエリ",
    "コマンドイベント",
    "クエリイベント",
    "時間イベント",
    "システムイベント",
    "値・指標",
    "状態",
    "データ",
    "方針・制約",
    "業務上の概念",
    "負荷特性",
    "設計上の概念",
}


class ContractError(ValueError):
    pass


def fail(message: str) -> None:
    raise ContractError(message)


def parse_frontmatter(text: str) -> tuple[int, str, str]:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if match is None:
        fail("用語定義にversionとsubjectを持つfrontmatterがありません")
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if not separator or not key.strip() or not value.strip():
            fail("用語定義のfrontmatterが不正です")
        key = key.strip()
        if key in values:
            fail(f"用語定義のfrontmatter keyが重複しています: {key}")
        values[key] = value.strip()
    if set(values) != {"version", "subject"}:
        fail("用語定義のfrontmatterはversionとsubjectだけを持たなければなりません")
    try:
        version = int(values["version"])
    except ValueError:
        fail("用語定義.versionは1以上の整数でなければなりません")
    if version < 1:
        fail("用語定義.versionは1以上の整数でなければなりません")
    return version, values["subject"], text[match.end():]


def validate_terminology_markdown(path: Path) -> tuple[int, dict[str, str]]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        fail(f"用語定義は絶対pathのregular fileでなければなりません: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        fail(f"用語定義をUTF-8 Markdownとして読めません: {exc}")
    version, subject, body = parse_frontmatter(text)
    if not subject:
        fail("用語定義.subjectは非空でなければなりません")
    if re.search(r"^\s*\|.*\|\s*$", body, re.MULTILINE):
        fail("用語定義はMarkdown表ではなく概念種別ごとの見出しで記載してください")
    if re.search(r"^#\s+\S", body, re.MULTILINE) is None:
        fail("用語定義に文書題名の見出しがありません")

    current_category: str | None = None
    terms: dict[str, dict[str, Any]] = {}
    current_term: str | None = None
    for raw_line in body.splitlines():
        category_match = re.match(r"^##\s+(.+?)\s*$", raw_line)
        if category_match:
            current_category = category_match.group(1)
            if current_category not in CATEGORIES:
                fail(f"未知の概念種別見出しです: {current_category}")
            current_term = None
            continue
        term_match = re.match(r"^###\s+(.+?)\s*$", raw_line)
        if term_match:
            if current_category is None:
                fail("用語見出しは概念種別見出しの下に置かなければなりません")
            current_term = term_match.group(1)
            if current_term in terms:
                fail(f"推奨用語名が重複しています: {current_term}")
            terms[current_term] = {"category": current_category, "lines": []}
            continue
        if current_term is not None:
            terms[current_term]["lines"].append(raw_line)
    if not terms:
        fail("用語定義に用語見出しが1件以上必要です")

    required_labels = {"状態", "根拠", "見直し条件"}
    for term, value in terms.items():
        lines = [line.strip() for line in value["lines"] if line.strip()]
        definition = [line for line in lines if not re.match(r"^-\s*(状態|根拠|見直し条件):", line)]
        if not definition:
            fail(f"用語に定義本文がありません: {term}")
        labels: dict[str, str] = {}
        for line in lines:
            match = re.match(r"^-\s*(状態|根拠|見直し条件):\s*(.+)$", line)
            if match:
                if match.group(1) in labels:
                    fail(f"用語の属性が重複しています: {term}.{match.group(1)}")
                labels[match.group(1)] = match.group(2)
        if set(labels) != required_labels:
            fail(f"用語に状態・根拠・見直し条件が必要です: {term}")
        if labels["状態"] not in {"合意済み", "暫定"}:
            fail(f"用語の状態は合意済みまたは暫定でなければなりません: {term}")
    return version, {term: value["category"] for term, value in terms.items()}


def load_markdown(path: Path) -> Document:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        fail(f"基準資料は絶対pathのregular fileでなければなりません: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        fail(f"基準資料をUTF-8 Markdownとして読めません: {exc}")
    try:
        return Document(text)
    except ValueError as exc:
        fail(f"基準資料の構文が不正です: {path}: {exc}")
    return Document("")


def validate_reference(
    artifact_path: Path,
    terminology_path: Path,
    terminology_version: int,
    terms: dict[str, str],
) -> None:
    document = load_markdown(artifact_path)
    if "用語" not in document.sections:
        fail(f"基準資料に `## 用語` 節がありません: {artifact_path}")
    try:
        locator, version, preferred = terminology_lines(document)
    except ValueError as exc:
        fail(f"{artifact_path}: {exc}")
        return
    if locator is None:
        fail(f"基準資料が用語定義を参照していません（`用語定義: なし`）: {artifact_path}")
        return
    if Path(locator).resolve() != terminology_path.resolve():
        fail(f"用語定義locatorが不一致です: {artifact_path}: {locator}")
    if version != terminology_version:
        fail(f"用語定義versionが不一致です: {artifact_path}: {version} != {terminology_version}")
    missing = sorted(set(preferred) - set(terms))
    if missing:
        fail(f"用語定義にない推奨用語名があります: {artifact_path}: {missing}")
    if "コマンドとクエリ" not in document.sections:
        return
    for table in tables(document.lines("コマンドとクエリ")):
        if table["header"][:2] != ["操作", "種別"]:
            continue
        for row in table["rows"]:
            if len(row) < 2:
                continue
            name, kind = strip_markup(row[0]), strip_markup(row[1])
            if kind not in ("コマンド", "クエリ"):
                continue
            if name not in terms:
                fail(f"用語定義にない操作名があります: {artifact_path}: {name}")
            if terms[name] != kind:
                fail(f"操作名の概念種別が用語定義と一致しません: {artifact_path}: {name} は用語定義では {terms[name]}、基準資料では {kind}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("check",))
    parser.add_argument("--terminology", required=True)
    parser.add_argument("--artifact", action="append", required=True)
    args = parser.parse_args()
    try:
        terminology_path = Path(args.terminology)
        version, terms = validate_terminology_markdown(terminology_path)
        for raw_path in args.artifact:
            validate_reference(Path(raw_path), terminology_path, version, terms)
    except ContractError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    print(str(terminology_path.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
