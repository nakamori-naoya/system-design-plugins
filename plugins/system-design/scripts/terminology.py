#!/usr/bin/env python3
"""Validate a heading-based terminology Markdown and artifact references."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


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


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        fail(f"成果物は絶対pathのregular fileでなければなりません: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"成果物をUTF-8 JSONとして読めません: {exc}")
    if not isinstance(value, dict):
        fail("成果物はJSON objectでなければなりません")
    return value


def parse_frontmatter(text: str) -> tuple[int, str, str]:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if match is None:
        fail("用語正本にversionとsubjectを持つfrontmatterがありません")
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if not separator or not key.strip() or not value.strip():
            fail("用語正本のfrontmatterが不正です")
        key = key.strip()
        if key in values:
            fail(f"用語正本のfrontmatter keyが重複しています: {key}")
        values[key] = value.strip()
    if set(values) != {"version", "subject"}:
        fail("用語正本のfrontmatterはversionとsubjectだけを持たなければなりません")
    try:
        version = int(values["version"])
    except ValueError:
        fail("用語正本.versionは1以上の整数でなければなりません")
    if version < 1:
        fail("用語正本.versionは1以上の整数でなければなりません")
    return version, values["subject"], text[match.end():]


def validate_terminology_markdown(path: Path) -> tuple[int, set[str]]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        fail(f"用語正本は絶対pathのregular fileでなければなりません: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        fail(f"用語正本をUTF-8 Markdownとして読めません: {exc}")
    version, subject, body = parse_frontmatter(text)
    if not subject or re.search(r"[ぁ-んァ-ヶ一-龯]", subject) is None:
        fail("用語正本.subjectは日本語でなければなりません")
    if re.search(r"^\s*\|.*\|\s*$", body, re.MULTILINE):
        fail("用語正本はMarkdown表ではなく概念種別ごとの見出しで記載してください")
    if re.search(r"^#\s+\S", body, re.MULTILINE) is None:
        fail("用語正本に文書題名の見出しがありません")

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
            if re.search(r"[ぁ-んァ-ヶ一-龯]", current_term) is None:
                fail(f"推奨用語名は日本語でなければなりません: {current_term}")
            if current_term in terms:
                fail(f"推奨用語名が重複しています: {current_term}")
            terms[current_term] = {"category": current_category, "lines": []}
            continue
        if current_term is not None:
            terms[current_term]["lines"].append(raw_line)
    if not terms:
        fail("用語正本に用語見出しが1件以上必要です")

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
    return version, set(terms)


def string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        fail(f"{label}は1件以上の配列でなければなりません")
    if not all(isinstance(item, str) and item.strip() for item in value):
        fail(f"{label}は非空文字列の配列でなければなりません")
    if len(set(value)) != len(value):
        fail(f"{label}に重複があります")
    return value


def validate_reference(
    artifact: dict[str, Any],
    artifact_path: Path,
    terminology_path: Path,
    terminology_version: int,
    preferred_terms: set[str],
) -> None:
    terminology = artifact.get("terminology")
    if not isinstance(terminology, dict) or set(terminology) != {"source", "usages"}:
        fail(f"成果物に有効なterminology参照がありません: {artifact_path}")
    source = terminology["source"]
    usages = terminology["usages"]
    if not isinstance(source, dict) or set(source) != {"locator", "version"}:
        fail(f"成果物のterminology.sourceが不正です: {artifact_path}")
    locator = source.get("locator")
    if not isinstance(locator, str) or not Path(locator).is_absolute() or Path(locator).resolve() != terminology_path.resolve():
        fail(f"用語正本locatorが不一致です: {artifact_path}")
    if source.get("version") != terminology_version:
        fail(f"用語正本versionが不一致です: {artifact_path}")
    if not isinstance(usages, list):
        fail(f"成果物のterminology.usagesが不正です: {artifact_path}")
    for usage in usages:
        if not isinstance(usage, dict) or set(usage) != {"subject_id", "preferred_terms"}:
            fail(f"terminology.usagesが不正です: {artifact_path}")
        refs = string_list(usage["preferred_terms"], f"{artifact_path}.preferred_terms")
        missing = sorted(set(refs) - preferred_terms)
        if missing:
            fail(f"用語正本にない推奨用語名があります: {artifact_path}: {missing}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check",))
    parser.add_argument("--terminology", required=True)
    parser.add_argument("--artifact", action="append", required=True)
    args = parser.parse_args()
    try:
        terminology_path = Path(args.terminology)
        version, preferred_terms = validate_terminology_markdown(terminology_path)
        for raw_path in args.artifact:
            artifact_path = Path(raw_path)
            validate_reference(
                load_json(artifact_path),
                artifact_path,
                terminology_path,
                version,
                preferred_terms,
            )
    except ContractError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    print(str(terminology_path.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
