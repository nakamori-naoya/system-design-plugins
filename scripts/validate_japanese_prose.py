#!/usr/bin/env python3
"""人間向け文章が日本語であり、機械値を壊していないことを検査する。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


JAPANESE = re.compile(r"[ぁ-んァ-ヶ一-龯]")
ID_OR_DATE = re.compile(r"^(?:[A-Z][A-Z0-9_-]*-[A-Za-z0-9_.-]+|20\d\d(?:-\d\d-\d\d|-Q[1-4])?)$")
HUMAN_KEYS = {
    "subject", "statement", "role", "interest", "problem", "desired_outcome",
    "observer", "verification_method", "owner", "question", "condition", "rationale",
    "choice", "service", "data", "label", "summary", "calculation", "verification_plan",
    "sensitivity", "population", "time_window", "context", "objective", "method",
    "expected_evidence", "cost_effect", "operability_effect", "rejection_reason",
    "failure_scope", "failure_behavior", "degradation_behavior", "detection", "recovery",
    "trigger", "impact", "title", "reason", "request", "must_not",
}
HUMAN_ARRAY_KEYS = {
    "advantages", "disadvantages", "risks", "positive_consequences",
    "negative_consequences", "follow_ups", "required", "must_not", "sources",
}
MACHINE_VALUES = {
    "aws", "gcp", "create_artifact", "create_ready_artifact", "stop_and_route",
}
SKILL_IDS = {
    "discover-requirements", "discover-workload-model",
    "discover-quality-requirements", "design-cloud-architecture",
}
BROKEN_TOKENS = {
    "deスクリプトion", "参照資料s/", "可用性_units", "time_時間窓",
    "design_設計感度", "category_網羅状況", "provider_解消内容",
}
NAKED_ENGLISH = (
    "actor", "action", "event", "payload", "latency", "throughput",
    "availability", "consistency", "durability", "recovery", "security",
    "privacy", "operability", "cost", "provider", "failure",
    "degradation", "node", "burst", "trade-off", "region", "application",
)


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def machine_like(value: str) -> bool:
    if value in MACHINE_VALUES or ID_OR_DATE.fullmatch(value):
        return True
    if value.startswith(("../", "./", "/")) or value.endswith((".json", ".yml", ".yaml")):
        return True
    return False


def human_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"https?://\S+", "", text)
    return text


def reject_naked_english(text: str, path: Path) -> None:
    prose = human_markdown(text)
    for token in NAKED_ENGLISH:
        if re.search(
            rf"(?<![A-Za-z0-9_-]){re.escape(token)}(?![A-Za-z0-9_-])",
            prose,
            re.IGNORECASE,
        ):
            fail(f"日本語化対象の裸の英語が残っています: {path}: {token}")


def inspect_json(value: object, path: str = "$", parent_key: str | None = None) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            inspect_json(child, f"{path}.{key}", key)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            inspect_json(child, f"{path}[{index}]", parent_key)
        return
    if not isinstance(value, str):
        return
    human = parent_key in HUMAN_KEYS or parent_key in HUMAN_ARRAY_KEYS
    if human and not JAPANESE.search(value) and not machine_like(value):
        fail(f"人間向け文字列が日本語ではありません: {path}: {value}")


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    markdown = [root / "README.md", root / "tests/fixtures/README.md"]
    markdown.extend(sorted((root / "plugins/system-design/skills").glob("*/SKILL.md")))
    markdown.extend(sorted((root / "plugins/system-design/skills").glob("*/references/*.md")))
    markdown.extend(sorted((root / "plugins/system-design/playbooks/system-design").glob("*/SKILL.md")))

    for path in markdown:
        text = path.read_text(encoding="utf-8")
        reject_naked_english(text, path)
        for token in BROKEN_TOKENS:
            if token in text:
                fail(f"破損した機械語が残っています: {path}: {token}")
        for heading in re.findall(r"^#{1,4}\s+(.+)$", text, re.MULTILINE):
            plain = re.sub(r"`[^`]+`", "", heading).strip()
            if plain and plain not in SKILL_IDS and not JAPANESE.search(plain):
                fail(f"人間向け見出しが日本語ではありません: {path}: {heading}")
        if path.name == "SKILL.md" and "\ndescription:" not in text:
            fail(f"frontmatterのdescriptionがありません: {path}")

    fixture_root = root / "tests/fixtures"
    for path in sorted(fixture_root.glob("*/*.json")):
        inspect_json(json.loads(path.read_text(encoding="utf-8")), str(path))

    architecture = json.loads(
        (fixture_root / "design-cloud-architecture/success.json").read_text(encoding="utf-8")
    )
    if not JAPANESE.search(architecture["diagram"]["source"]):
        fail("Mermaid構成図の表示名が日本語ではありません")

    for path in sorted((root / "plugins/system-design/playbooks/system-design").glob("*/playbook.yml")):
        text = path.read_text(encoding="utf-8")
        for key, value in re.findall(r"\b(description|directive|purpose):\s*([^,}\n]+)", text):
            plain = re.sub(r"`[^`]+`", "", value).strip()
            if plain and not JAPANESE.search(plain):
                fail(f"playbookの人間向け{key}が日本語ではありません: {path}: {plain}")
            for token in NAKED_ENGLISH:
                if re.search(
                    rf"(?<![A-Za-z0-9_-]){re.escape(token)}(?![A-Za-z0-9_-])",
                    plain,
                    re.IGNORECASE,
                ):
                    fail(f"playbookの人間向け{key}に裸の英語があります: {path}: {token}")

    readme = (root / "README.md").read_text(encoding="utf-8")
    required_audit = {"機械互換", "英語が通例", "日本語化", "判断保留"}
    missing = sorted(term for term in required_audit if term not in readme)
    if missing:
        fail(f"英語表記の監査分類が不足しています: {missing}")

    print("Japanese prose: passed")


if __name__ == "__main__":
    main()
