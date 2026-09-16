#!/usr/bin/env python3
"""system-design packageの公開入口と自己完結の構造契約を検査する。

見出しの形や個数、文章の良し悪しは検査しない（意味評価はagentが読む）。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


IDS = (
    "discover-requirements",
    "discover-workload-model",
    "discover-quality-requirements",
    "design-cloud-architecture",
)
LINK = re.compile(r"\[[^\]]+\]\((references/[^)#]+\.md)(?:#[^)]*)?\)")


class ValidationError(ValueError):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def regular(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        fail(f"{label}がregular fileではない: {path}")


def load_json(path: Path, label: str) -> dict:
    regular(path, label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"{label}をJSON objectとして読めない: {exc}")
    if not isinstance(value, dict):
        fail(f"{label}がJSON objectではない")
    return value


def load_yaml(path: Path, label: str) -> dict:
    regular(path, label)
    result = subprocess.run(
        ["yq", "-o=json", "-I=0", ".", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        fail(f"{label}をYAML objectとして読めない: {result.stderr.strip()}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(f"{label}のYAML parser出力をJSONとして読めない: {exc}")
    if not isinstance(value, dict):
        fail(f"{label}がYAML objectではない")
    return value


def skill_name(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        fail(f"SKILL.mdのYAML frontmatter開始が無い: {path}")
    try:
        end = lines.index("---", 1)
    except ValueError:
        fail(f"SKILL.mdのYAML frontmatter終端が無い: {path}")
    result = subprocess.run(
        ["yq", "-o=json", "-I=0", "."],
        input="\n".join(lines[1:end]) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        fail(f"SKILL.mdのYAML frontmatterを解析できない: {path}: {result.stderr.strip()}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(f"SKILL.mdのYAML parser出力が不正: {path}: {exc}")
    name = value.get("name") if isinstance(value, dict) else None
    if not isinstance(name, str) or not name:
        fail(f"SKILL.mdのfrontmatter nameが文字列ではない: {path}")
    return name


def marketplace(repository: Path, runtime: str) -> tuple[str, str, str]:
    path = repository / (".agents/plugins/marketplace.json" if runtime == "codex" else ".claude-plugin/marketplace.json")
    value = load_json(path, f"{runtime} marketplace")
    plugins = value.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1 or not isinstance(plugins[0], dict):
        fail(f"{runtime} marketplaceはpackage一件でなければならない")
    item = plugins[0]
    source = item.get("source")
    if runtime == "codex":
        if not isinstance(source, dict) or source.get("source") != "local":
            fail("Codex marketplace sourceがlocalではない")
        source = source.get("path")
    result = (item.get("name"), item.get("version"), source)
    if not all(isinstance(part, str) and part for part in result):
        fail(f"{runtime} marketplace identityが不正")
    return result  # type: ignore[return-value]


def validate_entry(package: Path, identifier: str) -> None:
    root = package / "skills" / identifier
    entry = root / "SKILL.md"
    regular(entry, f"{identifier}公開SKILL.md")
    text = entry.read_text(encoding="utf-8")
    name = skill_name(entry)
    if name != identifier:
        fail(f"{identifier}公開skill nameが不一致")
    links = LINK.findall(text)
    references = sorted((root / "references").glob("*.md"))
    if {root / link for link in links} != set(references):
        fail(f"{identifier}内部SKILL.mdから全referenceへ直接到達できない")
    for sibling in set(IDS) - {identifier}:
        if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(sibling)}(?![A-Za-z0-9_-])", text):
            fail(f"{identifier}内部skillが兄弟identityを参照している: {sibling}")
    if any(root.glob(".*-plugin/plugin.json")):
        fail(f"{identifier}直接公開skillに入口別runtime manifestは不要")


def validate_repository(repository: Path) -> None:
    if not repository.is_absolute() or repository.is_symlink() or not repository.is_dir():
        fail(f"repositoryは実在する絶対directoryでなければならない: {repository}")
    expected = ("system-design", "2.0.0", "./plugins/system-design")
    if marketplace(repository, "codex") != expected or marketplace(repository, "claude") != expected:
        fail("marketplace identityがruntime間またはpackageと一致しない")
    package = repository / "plugins/system-design"
    manifests = [load_json(package / f".{runtime}-plugin/plugin.json", f"package {runtime} manifest") for runtime in ("codex", "claude")]
    shared = [{key: item.get(key) for key in ("name", "version", "skills")} | {"harness": item.get("metadata", {}).get("harness")} for item in manifests]
    if shared[0] != shared[1]:
        fail("package runtime manifestが一致しない")
    manifest = manifests[0]
    harness = manifest.get("metadata", {}).get("harness", {})
    expected = [f"./skills/{identifier}" for identifier in IDS]
    if manifest.get("skills") != expected:
        fail("package skillsが直接公開skill 4件と一致しない")
    if "playbooks" in harness or "internalPlugins" in harness or "installationSurface" in harness or "implements" in harness:
        fail("自己完結skillの直接公開packageにplaybooks / internalPlugins / installationSurface / implementsは置かない")
    if harness.get("marketplace") != "system-design" or type(harness.get("contractVersion")) is not int:
        fail("metadata.harnessにmarketplace=system-designと整数contractVersionが要る")
    for identifier in IDS:
        validate_entry(package, identifier)
    print("Repository: passed (1 package, 4 directly published self-contained skills)")


def expect_rejected(repository: Path, label: str, needle: str, mutate) -> None:
    with tempfile.TemporaryDirectory(prefix="system-design-validator-") as value:
        candidate = Path(value) / "repository"
        shutil.copytree(repository, candidate, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        mutate(candidate)
        try:
            validate_repository(candidate)
        except (ValidationError, OSError, UnicodeError) as exc:
            if needle not in str(exc):
                fail(f"負例「{label}」が期待した理由で失敗しない: {exc}")
            print(f"Negative: passed ({label})")
        else:
            fail(f"負例「{label}」を拒否できない")


def self_test(repository: Path) -> None:
    validate_repository(repository)

    for label, replacement in (
        ("frontmatter nameのYAML comment", "name: discover-requirements # 公開identity"),
        ("frontmatter nameのquoted scalar", 'name: "discover-requirements"'),
    ):
        with tempfile.TemporaryDirectory(prefix="system-design-frontmatter-") as value:
            candidate = Path(value) / "repository"
            shutil.copytree(repository, candidate, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            path = candidate / "plugins/system-design/skills/discover-requirements/SKILL.md"
            path.write_text(path.read_text(encoding="utf-8").replace("name: discover-requirements", replacement, 1), encoding="utf-8")
            validate_repository(candidate)
            print(f"Positive: passed ({label})")

    def remove_entry(root: Path) -> None:
        (root / "plugins/system-design/skills/discover-requirements/SKILL.md").unlink()

    def rename_entry(root: Path) -> None:
        path = root / "plugins/system-design/skills/discover-workload-model/SKILL.md"
        path.write_text(path.read_text(encoding="utf-8").replace("name: discover-workload-model", "name: wrong-name", 1), encoding="utf-8")

    def body_only_name(root: Path) -> None:
        path = root / "plugins/system-design/skills/discover-requirements/SKILL.md"
        text = path.read_text(encoding="utf-8").replace("name: discover-requirements\n", "", 1)
        path.write_text(text + "\nname: discover-requirements\n", encoding="utf-8")

    def missing_name(root: Path) -> None:
        path = root / "plugins/system-design/skills/discover-requirements/SKILL.md"
        path.write_text(path.read_text(encoding="utf-8").replace("name: discover-requirements\n", "", 1), encoding="utf-8")

    expect_rejected(repository, "公開skill欠落", "regular fileではない", remove_entry)
    expect_rejected(repository, "公開skill identity不一致", "nameが不一致", rename_entry)
    expect_rejected(repository, "本文だけの偽name", "frontmatter name", body_only_name)
    expect_rejected(repository, "frontmatter name欠落", "frontmatter name", missing_name)
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
        raise SystemExit(f"FAIL: {exc}")
