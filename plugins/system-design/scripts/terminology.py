#!/usr/bin/env python3
"""用語定義（Markdown）と、それを参照する基準資料（Markdown）の整合を検査する。

  python3 terminology.py check --terminology <用語定義の絶対path> --artifact <基準資料Markdownの絶対path> [--artifact ...]

見出しの文言は読まない。読むのは次の目印だけである。
  - 用語定義: frontmatter（version / subject）、`### <推奨用語名>` の見出し（用語の識別子）、その下の `- 種別:` `- 状態:` `- 根拠:` `- 見直し条件:` の行。
    H2 は読み手のための自由な見出しで、種別を表さない。
  - 参照側の基準資料: 資料のどこかに1つだけある `用語定義: <絶対path> 版: <整数>`（または `用語定義: なし`）の行と `推奨用語名: <名>、<名>` の行、
    見出し行が `| 操作 | 種別 |` で始まる表。
通ったときに言えるのは次だけである。

  - 用語定義が表を使わず、重複しない推奨用語名を `###` で置き、各用語が定義本文と、既知の種別・状態・根拠・見直し条件を持つ
  - 各参照側基準資料の `用語定義:` の行が同じ用語定義（path）と同じ版を指し、`推奨用語名:` の名前がすべて用語定義にある
  - 参照側基準資料に操作の表があれば、種別が コマンド / クエリ の操作名が用語定義の同じ種別（コマンド / クエリ）の推奨用語名である

正例: tests/fixtures/terminology/success.md と artifact.md。反例と境界例: tests/test_terminology.py（版の不一致、未登録の推奨用語名、用語定義: なし、
  所在の不一致、`用語定義:` の行が2つ、操作名の不一致と種別の不一致、推奨用語名の重複、表、未知の種別、種別の行の欠落。境界例: 見出しに結論を入れた資料）。
意味評価として残す範囲: 用語の定義と種別の分け方が妥当か、本文の語が推奨用語名と一致しているか。

exit 0 = 通った（stdoutに用語定義の絶対path） / 2 = 述語が成り立たない（診断は標準エラー `FAIL: <理由>`）。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canon import Document, prose_lines, strip_markup, tables, terminology_lines  # noqa: E402  package共有の構文解析


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
        fail("用語定義はMarkdown表ではなく、用語ごとの `###` 見出しと `- 種別:` の行で記載してください")
    if re.search(r"^#\s+\S", body, re.MULTILINE) is None:
        fail("用語定義に文書題名の見出しがありません")

    terms: dict[str, dict[str, Any]] = {}
    current_term: str | None = None
    for raw_line in body.splitlines():
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", raw_line)
        if heading and len(heading.group(1)) <= 2:
            current_term = None
            continue
        if heading and len(heading.group(1)) == 3:
            current_term = heading.group(2)
            if current_term in terms:
                fail(f"推奨用語名が重複しています: {current_term}")
            terms[current_term] = {"lines": []}
            continue
        if current_term is not None:
            terms[current_term]["lines"].append(raw_line)
    if not terms:
        fail("用語定義に `### <推奨用語名>` の用語が1件以上必要です")

    required_labels = {"種別", "状態", "根拠", "見直し条件"}
    for term, value in terms.items():
        lines = [line.strip() for line in value["lines"] if line.strip()]
        definition = [line for line in lines if not re.match(r"^-\s*(種別|状態|根拠|見直し条件):", line)]
        if not definition:
            fail(f"用語に定義本文がありません: {term}")
        labels: dict[str, str] = {}
        for line in lines:
            match = re.match(r"^-\s*(種別|状態|根拠|見直し条件):\s*(.+)$", line)
            if match:
                if match.group(1) in labels:
                    fail(f"用語の属性が重複しています: {term}.{match.group(1)}")
                labels[match.group(1)] = match.group(2)
        if set(labels) != required_labels:
            fail(f"用語に種別・状態・根拠・見直し条件が必要です: {term}")
        if labels["種別"] not in CATEGORIES:
            fail(f"未知の種別です: {term}: {labels['種別']}")
        if labels["状態"] not in {"合意済み", "暫定"}:
            fail(f"用語の状態は合意済みまたは暫定でなければなりません: {term}")
        value["category"] = labels["種別"]
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
    for table in tables(prose_lines(document)):
        if [strip_markup(cell) for cell in table["header"][:2]] != ["操作", "種別"]:
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
                fail(f"操作名の種別が用語定義と一致しません: {artifact_path}: {name} は用語定義では {terms[name]}、基準資料では {kind}")


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
