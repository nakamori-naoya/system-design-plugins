#!/usr/bin/env python3
"""Validate the distributable system-design package and its responsibility boundaries."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Callable

PACKAGE_NAME = "system-design"
VERSION = "0.1.0"
EXPECTED_SKILLS = {
    "discover-requirements",
    "discover-workload-model",
    "discover-quality-requirements",
    "design-cloud-architecture",
}
INTERNAL_SKILL_NAMES = {name: f"internal-{name}" for name in EXPECTED_SKILLS}
EXPECTED_PLAYBOOK_PATHS = {
    name: f"./playbooks/system-design/{name}" for name in EXPECTED_SKILLS
}
REQUIRED_HEADINGS = (
    "入力",
    "出力",
    "非責務",
    "開始条件",
    "停止条件",
    "完了条件",
    "後続成果物への追跡",
)
CLOUD_REQUIRED_TERMS = (
    "クラウド・サービス選定",
    "代替案比較",
    "ADR",
    "編集可能なインフラ構成図",
    "要求トレーサビリティ",
)
SOURCE_LEAKS = (
    re.compile(r"/(?:Users|home)/[^\s`]+/(?:\.codex|\.claude)[^\s`]*?/plugins/cache/"),
    re.compile(r"(?:^|[\s`])~/(?:\.codex|\.claude)[^\s`]*?/plugins/cache/"),
)
EXPECTED_OUTPUT_ROOTS = {
    "discover-requirements": "system-design/requirements/",
    "discover-workload-model": "system-design/workloads/",
    "discover-quality-requirements": "system-design/quality-requirements/",
    "design-cloud-architecture": "system-design/architectures/",
}
EXPECTED_DOCUMENT_TYPES = {
    "discover-requirements": "requirements-discovery",
    "discover-workload-model": "workload-model",
    "discover-quality-requirements": "quality-requirements",
    "design-cloud-architecture": "cloud-architecture",
}
EXPECTED_DOCUMENT_NAMES = {
    "discover-requirements": "requirements-discovery.md",
    "discover-workload-model": "workload-model.md",
    "discover-quality-requirements": "quality-requirements.md",
    "design-cloud-architecture": "cloud-architecture.md",
}
EXPECTED_ARTIFACT_VALUES = {
    "discover-requirements": "requirements_artifact",
    "discover-workload-model": "workload_artifact",
    "discover-quality-requirements": "quality_artifact",
    "design-cloud-architecture": "architecture_artifact",
}
PLAYBOOK_PUBLIC_INPUTS = {"request", "referenced_artifacts", "run_root", "target_repository", "document_destination"}


class ValidationError(ValueError):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def require_regular(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        fail(f"{label}がありません: {path}: {exc}")
    if path.is_symlink() or not stat.S_ISREG(mode) or path.stat().st_size == 0:
        fail(f"{label}は非空のregular fileでなければなりません: {path}")


def load_json(path: Path, label: str) -> dict:
    require_regular(path, label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"{label}が有効なJSONではありません: {exc}")
    if not isinstance(value, dict):
        fail(f"{label}はJSON objectでなければなりません")
    return value


def reject_symlinks(root: Path) -> None:
    if root.is_symlink():
        fail(f"配布packageがsymlinkです: {root}")
    for directory, subdirectories, filenames in os.walk(root, followlinks=False):
        parent = Path(directory)
        for name in [*subdirectories, *filenames]:
            if (parent / name).is_symlink():
                fail(f"配布package内にsymlinkがあります: {parent / name}")


def normalized_catalog(root: Path, runtime: str) -> tuple[str, dict[str, str]]:
    relative = (
        ".agents/plugins/marketplace.json"
        if runtime == "codex"
        else ".claude-plugin/marketplace.json"
    )
    path = root / relative
    catalog = load_json(path, f"{runtime} marketplace")
    plugins = catalog.get("plugins")
    if (
        not isinstance(plugins, list)
        or len(plugins) != 1
        or not isinstance(plugins[0], dict)
    ):
        fail(f"{runtime} marketplaceの公開インストール対象は1件でなければなりません")
    entry = plugins[0]
    source = entry.get("source")
    if runtime == "codex":
        if not isinstance(source, dict) or source.get("source") != "local":
            fail("Codex marketplace sourceはlocal objectでなければなりません")
        source = source.get("path")
        policy = entry.get("policy")
        expected_policy = {
            "installation": "AVAILABLE",
            "authentication": "ON_INSTALL",
        }
        if policy != expected_policy:
            fail("Codex marketplace policyが配布規約と一致しません")
        if not isinstance(entry.get("category"), str) or not entry["category"]:
            fail("Codex marketplace categoryがありません")
    identity = {
        "name": entry.get("name"),
        "version": entry.get("version"),
        "source": source,
    }
    if any(not isinstance(value, str) or not value for value in identity.values()):
        fail(f"{runtime} marketplace identityが不正です")
    if catalog.get("name") != PACKAGE_NAME:
        fail(f"{runtime} marketplace名が{PACKAGE_NAME}ではありません")
    return catalog["name"], identity


def validate_manifests(package: Path, expected_identity: dict[str, str]) -> None:
    manifests = []
    for runtime in ("codex", "claude"):
        path = package / f".{runtime}-plugin/plugin.json"
        data = load_json(path, f"{runtime} plugin manifest")
        manifests.append(data)
        if (
            data.get("name") != expected_identity["name"]
            or data.get("version") != expected_identity["version"]
        ):
            fail(f"{runtime} plugin manifest identityがmarketplaceと一致しません")
        if data.get("skills") != [
            EXPECTED_PLAYBOOK_PATHS[name]
            for name in (
                "discover-requirements",
                "discover-workload-model",
                "discover-quality-requirements",
                "design-cloud-architecture",
            )
        ]:
            fail(f"{runtime} plugin manifestの公開playbook集合が不正です")
        if not isinstance(data.get("description"), str) or not data["description"].strip():
            fail(f"{runtime} plugin manifest descriptionがありません")
        author = data.get("author")
        if (
            not isinstance(author, dict)
            or not isinstance(author.get("name"), str)
            or not author["name"].strip()
        ):
            fail(f"{runtime} plugin manifest authorがありません")
    if manifests[0] != manifests[1]:
        fail("Claude/Codex plugin manifestの内容が一致しません")
    interface = manifests[0].get("interface")
    required = {
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "capabilities",
        "defaultPrompt",
    }
    if not isinstance(interface, dict) or not required.issubset(interface):
        fail("plugin interface metadataが不足しています")
    if "Skills" not in interface.get("capabilities", []):
        fail("playbook packageのSkills capabilityがありません")
    harness = manifests[0].get("metadata", {}).get("harness", {})
    if harness.get("installationSurface") != "playbook-package":
        fail("installationSurfaceがplaybook-packageではありません")
    if harness.get("marketplace") != PACKAGE_NAME:
        fail("manifestのmarketplace identityが不正です")
    if harness.get("playbooks") != EXPECTED_PLAYBOOK_PATHS:
        fail("manifestのplaybook公開mapが不正です")
    expected_internal = {name: f"./skills/{name}" for name in EXPECTED_SKILLS}
    if harness.get("internalPlugins") != expected_internal:
        fail("manifestのinternalPlugins mapが不正です")


def validate_playbooks(package: Path) -> None:
    root = package / "playbooks/system-design"
    discovered = {path.parent.name for path in root.glob("*/playbook.yml")}
    if discovered != EXPECTED_SKILLS:
        fail(f"公開playbook集合が4件と一致しません: {sorted(discovered)}")
    for name in sorted(EXPECTED_SKILLS):
        playbook = root / name
        for relative in (
            "playbook.yml", "SKILL.md", "scripts/prepare.sh", "scripts/resolve.sh",
            "scripts/ground.py", "scripts/material.py", "scripts/verify.py", "scripts/cleanup.py",
            "scripts/plan-cleanup.py",
            ".codex-plugin/plugin.json", ".claude-plugin/plugin.json",
        ):
            require_regular(playbook / relative, f"{name} playbook {relative}")
        frontmatter = parse_frontmatter(
            (playbook / "SKILL.md").read_text(encoding="utf-8"),
            playbook / "SKILL.md",
        )
        if frontmatter.get("name") != name:
            fail(f"{name} playbookの公開SKILL名が不正です")
        text = (playbook / "playbook.yml").read_text(encoding="utf-8")
        required = (
            "version: 2", f"name: {name}", f"plugin: {name}",
            "marketplace: system-design", f"skill: {name}",
            "plugin: grill", "marketplace: grill", "plugin: write-doc",
            "marketplace: write-doc", "playbook: grill", "playbook: write-doc",
            "script: scripts/ground.py", "script: scripts/material.py",
            "script: scripts/verify.py", "output_format: markdown",
            "status: ${verification_report.status}",
            "open_questions: ${verification_report.open_questions}",
            "handoff: ${verification_report.handoff}", "readyとunresolvedの双方",
            "always_run: true",
        )
        for token in required:
            if token not in text:
                fail(f"{name} playbookの契約が不足しています: {token}")
        document_type = EXPECTED_DOCUMENT_TYPES[name]
        if text.count(f"document_type: {document_type}") != 2:
            fail(
                f"{name} playbookは型{document_type}を公開宣言とdocument入力へ"
                "一度ずつ明示しなければなりません"
            )
        expected_name = EXPECTED_DOCUMENT_NAMES[name]
        if text.count(f"new_name: {expected_name}") != 1:
            fail(f"{name} playbookのwrite-doc用ASCII nameが不正です")
        if re.search(r"id:\s*document[^\n]*when:", text):
            fail(f"{name} playbookはunresolved時にdocumentをskipできません")
        cleanup_token = "script: scripts/finalize.sh" if name == "design-cloud-architecture" else "script: scripts/cleanup.py"
        if cleanup_token not in text:
            fail(f"{name} playbookのcleanup工程が不足しています")
        step_lines = [line.strip() for line in text.splitlines() if line.strip().startswith("- {id:")]
        if not step_lines or any("needs:" not in line or "provides:" not in line for line in step_lines):
            fail(f"{name} playbookの全工程にneeds/providesが必要です")
        validate_step_graph(name, step_lines)
        validate_step_cli_contract(name, playbook, step_lines)
        common_order = ("id: settle", "id: ground", "skill: " + name,
                        "id: material", "id: verify", "id: document")
        positions = [text.find(token) for token in common_order]
        if any(position < 0 for position in positions) or positions != sorted(positions):
            fail(f"{name} playbookのsettle/ground/skill/material/verify/document順が不正です")
        for runtime in ("codex", "claude"):
            manifest = load_json(
                playbook / f".{runtime}-plugin/plugin.json",
                f"{name} {runtime} playbook manifest",
            )
            if manifest.get("name") != name or manifest.get("skills") != "./":
                fail(f"{name} {runtime} playbook manifestが不正です")
        for runtime in ("codex", "claude"):
            internal = load_json(
                package / f"skills/{name}/.{runtime}-plugin/plugin.json",
                f"{name} {runtime} internal manifest",
            )
            if internal.get("name") != name or internal.get("skills") != "./":
                fail(f"{name} {runtime} internal manifestが不正です")
    architecture = (root / "design-cloud-architecture/playbook.yml").read_text(
        encoding="utf-8"
    )
    ordered = [
        architecture.find("id: prepare-provider"),
        architecture.find("id: resolve-provider"),
        architecture.find("id: design,"),
        architecture.find("id: finalize-provider"),
    ]
    if any(index < 0 for index in ordered) or ordered != sorted(ordered):
        fail("architecture playbookのprepare/resolve/design/finalize順が不正です")
    if "always_run: true" not in architecture or "finally_step: finalize-provider" not in architecture:
        fail("architecture playbookの後片付け契約がありません")
    require_regular(
        root / "design-cloud-architecture/scripts/finalize.sh",
        "architecture playbook finalize.sh",
    )
    for path in root.glob("*/playbook.yml"):
        targets = re.findall(r"playbook:\s*([A-Za-z0-9_-]+)", path.read_text(encoding="utf-8"))
        if any(target not in {"grill", "write-doc"} for target in targets):
            fail(f"playbook間に循環し得る内部呼出しがあります: {path}")


def inline_value(line: str, key: str) -> str:
    match = re.search(rf"(?:^|[,{{])\s*{re.escape(key)}:\s*([^,}}]+)", line)
    if match is None:
        fail(f"playbook工程に{key}がありません: {line}")
    return match.group(1).strip()


def inline_list(line: str, key: str) -> list[str]:
    match = re.search(rf"(?:^|[,{{])\s*{re.escape(key)}:\s*\[([^]]*)\]", line)
    if match is None:
        fail(f"playbook工程に{key}配列がありません: {line}")
    values = [value.strip() for value in match.group(1).split(",") if value.strip()]
    if len(values) != len(set(values)):
        fail(f"playbook工程の{key}に重複があります: {line}")
    return values


def validate_step_graph(name: str, step_lines: list[str]) -> None:
    """needs/providesだけで供給元と順序を一意に検査する。"""
    steps = []
    providers: dict[str, tuple[int, str]] = {}
    ids: set[str] = set()
    for index, line in enumerate(step_lines):
        identifier = inline_value(line, "id")
        if identifier in ids:
            fail(f"{name} playbookの工程IDが重複しています: {identifier}")
        ids.add(identifier)
        needs = inline_list(line, "needs")
        provides = inline_list(line, "provides")
        for value in provides:
            if value in PLAYBOOK_PUBLIC_INPUTS:
                fail(f"{name} playbookが公開入力を重複供給しています: {value}")
            if value in providers:
                fail(f"{name} playbookの成果供給元が重複しています: {value}")
            providers[value] = (index, identifier)
        steps.append((identifier, needs, provides))
    for index, (identifier, needs, provides) in enumerate(steps):
        for value in needs:
            if value in provides:
                fail(f"{name} playbookの自己参照cycle: {identifier}/{value}")
            if value in PLAYBOOK_PUBLIC_INPUTS:
                continue
            source = providers.get(value)
            if source is None:
                fail(f"{name} playbookの未知の必須入力: {identifier}/{value}")
            if source[0] >= index:
                fail(f"{name} playbookの前方参照cycle: {source[1]} -> {identifier}/{value}")


def required_cli_flags(path: Path, visited: set[Path] | None = None) -> set[str]:
    """Python wrapperが委譲する共通CLIまで追って必須flagを得る。"""
    path = path.resolve()
    visited = set() if visited is None else visited
    if path in visited:
        fail(f"CLI wrapperが循環しています: {path}")
    visited.add(path)
    text = path.read_text(encoding="utf-8")
    flags = set(
        re.findall(
            r"add_argument\(\s*['\"](--[a-z0-9-]+)['\"][^)]*"
            r"required\s*=\s*True",
            text,
            re.DOTALL,
        )
    )
    wrapper = re.search(
        r"Path\(__file__\)\.resolve\(\)\.parents\[(\d+)\]"
        r"\s*/\s*['\"]scripts['\"]\s*/\s*['\"]([^'\"]+)['\"]",
        text,
        re.DOTALL,
    )
    if wrapper is not None:
        target = path.parents[int(wrapper.group(1))] / "scripts" / wrapper.group(2)
        require_regular(target, f"CLI wrapper target ({path})")
        flags |= required_cli_flags(target, visited)
    return flags


def validate_step_cli_contract(name: str, playbook: Path, step_lines: list[str]) -> None:
    """全直接実行工程の必須CLI入力をneedsへ対応付ける。"""
    artifact = EXPECTED_ARTIFACT_VALUES[name]
    expected = {
        "plan-cleanup": {
            "script": "scripts/plan-cleanup.py",
            "flags": {"--run-root", "--output"},
            "needs": {"run_root"},
        },
        "ground": {
            "script": "scripts/ground.py",
            "flags": {"--input", "--output"},
            "needs": {"request", "referenced_artifacts", "decisions", "open_questions"},
        },
        "material": {
            "script": "scripts/material.py",
            "flags": {"--grounded", "--artifact", "--output"},
            "needs": {"grounded_input", artifact},
        },
        "verify": {
            "script": "scripts/verify.py",
            "flags": {"--grounded", "--material", "--output"},
            "needs": {"grounded_input", "material"},
        },
        "cleanup": {
            "script": "scripts/cleanup.py",
            "flags": {"--manifest", "--output"},
            "needs": {"cleanup_manifest"},
        },
    }
    if name == "design-cloud-architecture":
        expected["ground"]["needs"].add("provider_resolution")
        expected.update({
            "prepare-provider": {
                "script": "scripts/prepare.sh",
                "flags": None,
                "needs": {"target_repository"},
            },
            "resolve-provider": {
                "script": "scripts/resolve.sh",
                "flags": None,
                "needs": {"runtime_config_path"},
            },
            "finalize-provider": {
                "script": "scripts/finalize.sh",
                "flags": None,
                "needs": {"cleanup_manifest"},
            },
        })
        expected.pop("cleanup")
    indexed = {inline_value(line, "id"): line for line in step_lines}
    scripted = {
        identifier for identifier, line in indexed.items()
        if re.search(r"(?:^|[,\{])\s*script\s*:", line)
    }
    if scripted != set(expected):
        fail(
            f"{name} playbookの直接実行工程集合がCLI契約と一致しません: "
            f"expected={sorted(expected)}, actual={sorted(scripted)}"
        )
    for identifier, contract in expected.items():
        line = indexed.get(identifier)
        if line is None:
            fail(f"{name} playbookに必須直接実行工程がありません: {identifier}")
        script = inline_value(line, "script")
        if script != contract["script"]:
            fail(
                f"{name} playbookの{identifier}実行scriptが不正です: "
                f"expected={contract['script']}, actual={script}"
            )
        script_path = playbook / script
        require_regular(script_path, f"{name} {identifier} script")
        expected_flags = contract["flags"]
        actual_flags = required_cli_flags(script_path) if expected_flags is not None else None
        if actual_flags != expected_flags:
            fail(
                f"{name} playbookの{identifier}必須CLI契約が不明です: "
                f"expected={sorted(expected_flags)}, actual={sorted(actual_flags)}"
            )
        needs = set(inline_list(line, "needs"))
        missing = sorted(contract["needs"] - needs)
        if missing:
            fail(
                f"{name} playbookの{identifier}必須CLI入力がneedsにありません: "
                f"{', '.join(missing)}"
            )


def unquote_yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_frontmatter(text: str, path: Path) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        fail(f"SKILL.mdにfrontmatterがありません: {path}")
    try:
        end = next(
            index
            for index, line in enumerate(lines[1:], 1)
            if line.strip() == "---"
        )
    except StopIteration:
        fail(f"SKILL.mdのfrontmatterが閉じていません: {path}")
    value: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1].isspace() or ":" not in line:
            fail(f"SKILL.mdのfrontmatterは単純なkey/valueでなければなりません: {path}")
        key, raw = line.split(":", 1)
        key = key.strip()
        if not key or key in value:
            fail(f"SKILL.mdのfrontmatter keyが不正または重複しています: {path}")
        value[key] = unquote_yaml_scalar(raw)
    return value


def validate_skills(package: Path) -> None:
    skills_root = package / "skills"
    if not skills_root.is_dir() or skills_root.is_symlink():
        fail("skills directoryがありません")
    discovered = {
        path.parent.name
        for path in skills_root.glob("*/SKILL.md")
        if path.is_file()
    }
    if discovered != EXPECTED_SKILLS:
        missing = sorted(EXPECTED_SKILLS - discovered)
        extra = sorted(discovered - EXPECTED_SKILLS)
        fail(
            "公開skill集合が4件と一致しません: "
            f"missing={missing}, extra={extra}"
        )
    for name in sorted(EXPECTED_SKILLS):
        path = skills_root / name / "SKILL.md"
        require_regular(path, f"{name} SKILL.md")
        text = path.read_text(encoding="utf-8")
        if "[TODO:" in text or len(text.strip()) < 300:
            fail(f"{name} SKILL.mdが未実装または短すぎます")
        frontmatter = parse_frontmatter(text, path)
        if frontmatter.get("name") != INTERNAL_SKILL_NAMES[name]:
            fail(f"{name} SKILL.mdの内部nameが不正です")
        if (
            not isinstance(frontmatter.get("description"), str)
            or not frontmatter["description"].strip()
        ):
            fail(f"{name} SKILL.mdのdescriptionがありません")
        for heading in REQUIRED_HEADINGS:
            if (
                re.search(
                    rf"^##\s+{re.escape(heading)}\s*$",
                    text,
                    re.MULTILINE,
                )
                is None
            ):
                fail(f"{name} SKILL.mdに必須節「{heading}」がありません")
        if name == "design-cloud-architecture":
            for term in CLOUD_REQUIRED_TERMS:
                if term not in text:
                    fail(f"design-cloud-architectureの必須成果物がありません: {term}")
        output_root = EXPECTED_OUTPUT_ROOTS[name]
        if output_root not in text:
            fail(f"{name}の固有出力rootがありません: {output_root}")


def validate_skill_independence(package: Path) -> None:
    skills_root = package / "skills"
    for path in sorted(skills_root.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if re.search(r"playbook|プレイブック", text, re.IGNORECASE):
            fail(f"内部skill Markdownに構成単位への言及があります: {path}")
        relative = path.relative_to(skills_root)
        owner = relative.parts[0] if relative.parts[0] in EXPECTED_SKILLS else None
        forbidden_names = EXPECTED_SKILLS - ({owner} if owner else set())
        for other in sorted(forbidden_names):
            if re.search(
                rf"(?<![A-Za-z0-9_-]){re.escape(other)}(?![A-Za-z0-9_-])",
                text,
            ):
                fail(f"内部skill Markdownが兄弟skill名を参照しています: {path}: {other}")
    for name in sorted(EXPECTED_SKILLS):
        root = skills_root / name
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".md", ".py", ".sh", ".json"}:
                continue
            text = path.read_text(encoding="utf-8")
            for other in EXPECTED_SKILLS - {name}:
                internal_refs = (f"skills/{other}/", f"../{other}/")
                if any(reference in text for reference in internal_refs):
                    fail(f"{name}が{other}の内部pathへ依存しています: {path}")


def validate_runtime_config_contract(package: Path) -> None:
    required = (
        "config/defaults.yml",
        "scripts/prepare.sh",
        "scripts/resolve.sh",
        "scripts/finalize.sh",
        "scripts/run-config.py",
    )
    for relative in required:
        require_regular(package / relative, f"runtime config {relative}")
    defaults = (package / "config/defaults.yml").read_text(encoding="utf-8")
    if re.search(r"^\s*provider:\s*(?:\"\"|'')\s*$", defaults, re.MULTILINE) is None:
        fail("bundled runtime configはproviderを空にして暗黙defaultを拒否しなければなりません")
    finalizer = (package / "scripts/finalize.sh").read_text(encoding="utf-8")
    for term in ("aws|gcp", "cloud.providerが未指定", "cloud.providerが不正"):
        if term not in finalizer:
            fail(f"runtime config provider検査が不足しています: {term}")


def yaml_section_items(text: str, section: str, path: Path) -> list[list[str]]:
    lines = text.splitlines()
    start = None
    section_indent = 0
    for index, raw in enumerate(lines):
        code = raw.split("#", 1)[0].rstrip()
        match = re.match(rf"^(\s*){re.escape(section)}\s*:\s*(.*)$", code)
        if match:
            if match.group(2).strip() not in {"", "[]"}:
                fail(f"{section}はblock配列または[]でなければなりません: {path}")
            if match.group(2).strip() == "[]":
                return []
            start = index + 1
            section_indent = len(match.group(1))
            break
    if start is None:
        return []
    items: list[list[str]] = []
    current: list[str] | None = None
    for raw in lines[start:]:
        code = raw.split("#", 1)[0].rstrip()
        if not code.strip():
            continue
        indent = len(code) - len(code.lstrip())
        if indent <= section_indent:
            break
        stripped = code.strip()
        if stripped.startswith("-"):
            current = [stripped[1:].strip()]
            items.append(current)
        elif current is None:
            fail(f"{section}にlist itemではない値があります: {path}")
        else:
            current.append(stripped)
    return items


def simple_mapping(lines: list[str], section: str, path: Path) -> dict[str, str]:
    joined = " ".join(lines).strip()
    if joined.startswith("{") and joined.endswith("}"):
        joined = joined[1:-1]
    pairs = re.findall(
        r"(?:^|[,\s])([A-Za-z][A-Za-z0-9_-]*)\s*:\s*"
        r"([^,{}\s]+)",
        joined,
    )
    mapping = {key: unquote_yaml_scalar(value) for key, value in pairs}
    if not mapping and joined:
        fail(f"{section} itemがmappingではありません: {path}")
    return mapping


def validate_dependency_boundaries(package: Path) -> None:
    for path in sorted(package.rglob("playbook.yml")):
        require_regular(path, "playbook.yml")
        text = path.read_text(encoding="utf-8")
        requires = [
            simple_mapping(item, "requires", path)
            for item in yaml_section_items(text, "requires", path)
        ]
        external: set[str] = set()
        for item in requires:
            if set(item) != {"plugin", "marketplace"}:
                fail(
                    "外部依存はpluginとmarketplaceだけを"
                    f"宣言しなければなりません: {path}"
                )
            plugin, marketplace = item.get("plugin"), item.get("marketplace")
            if not plugin or not marketplace:
                fail(f"外部依存identityが不正です: {path}")
            if marketplace != PACKAGE_NAME:
                if plugin != marketplace:
                    fail(f"外部repositoryには公開package名でだけ依存できます: {path}")
                external.add(plugin)
        steps = [
            simple_mapping(item, "steps", path)
            for item in yaml_section_items(text, "steps", path)
        ]
        for step in steps:
            if step.get("skill") in external or step.get("plugin") in external:
                fail(f"外部packageをskill/plugin工程で参照しています: {path}")
            referenced = {
                value for value in step.values() if isinstance(value, str)
            } & external
            if referenced and step.get("playbook") not in external:
                fail(f"外部packageはplaybook工程からだけ参照できます: {path}")


def reject_source_checkout_dependencies(package: Path) -> None:
    suffixes = {".md", ".json", ".yaml", ".yml", ".py", ".sh"}
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            continue
        for pattern in SOURCE_LEAKS:
            if pattern.search(text):
                fail(f"配布物がinstall cacheの絶対pathへ依存しています: {path}")


def validate_repository(root: Path) -> None:
    root = root.resolve(strict=True)
    for relative in ("AGENTS.md", "README.md", "LICENSE", "scripts/validate.sh"):
        require_regular(root / relative, relative)
    package = root / "plugins/system-design"
    if not package.is_dir() or package.is_symlink():
        fail("配布package plugins/system-designがありません")
    reject_symlinks(package)
    require_regular(package / "LICENSE", "package LICENSE")
    if (root / "LICENSE").read_bytes() != (package / "LICENSE").read_bytes():
        fail("package LICENSEがroot LICENSEと一致しません")
    plugin_roots = {
        path.parent.parent.relative_to(root).as_posix()
        for path in (root / "plugins").glob("*/.codex-plugin/plugin.json")
    }
    if plugin_roots != {"plugins/system-design"}:
        fail(f"公開package集合が1件と一致しません: {sorted(plugin_roots)}")
    codex_name, codex_identity = normalized_catalog(root, "codex")
    claude_name, claude_identity = normalized_catalog(root, "claude")
    if codex_name != claude_name or codex_identity != claude_identity:
        fail("Claude/Codex marketplace metadataの内容が一致しません")
    expected_identity = {
        "name": PACKAGE_NAME,
        "version": VERSION,
        "source": "./plugins/system-design",
    }
    if codex_identity != expected_identity:
        fail("marketplace identityが配布packageと一致しません")
    validate_manifests(package, codex_identity)
    validate_playbooks(package)
    validate_skills(package)
    validate_skill_independence(package)
    validate_runtime_config_contract(package)
    validate_dependency_boundaries(package)
    reject_source_checkout_dependencies(package)
    print("Repository: passed (1 package, 4 public playbooks, 4 internal skills)")


def fixture_skill(name: str) -> str:
    if name == "design-cloud-architecture":
        output = "\n".join(f"- {term}" for term in CLOUD_REQUIRED_TERMS)
    else:
        output = "- 固有成果物を根拠付きで保存する"
    output_root = EXPECTED_OUTPUT_ROOTS[name]
    return f"""---
name: {INTERNAL_SKILL_NAMES[name]}
description: 検証器の自己試験に用いる十分な説明を持つfixture skill
---
# {name}

## 入力
根拠、対象、版、状態が明示された入力を受け取る。

## 出力
{output}
{output_root}<slug>へ固有成果物を保存する。

## 非責務
隣接する責務や実装を確定しない。

## 開始条件
対象と根拠を識別できる場合に開始する。

## 停止条件
意味を変える未決があれば確定作業を停止する。

## 完了条件
成果物の状態、未決、検証済み範囲を観測できる。

## 後続成果物への追跡
入力ID、出力ID、影響先、再確認条件を残す。仮説を事実へ昇格せず、保存済みと後続readyを区別する。
"""


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def expect_rejected(
    fixture: Path,
    name: str,
    expected: str,
    mutate: Callable[[Path], None],
) -> None:
    with tempfile.TemporaryDirectory(prefix="system-design-negative-") as temporary:
        candidate = Path(temporary) / "repository"
        shutil.copytree(fixture, candidate, symlinks=True)
        mutate(candidate)
        try:
            validate_repository(candidate)
        except (OSError, UnicodeError, ValidationError) as exc:
            if expected not in str(exc):
                fail(f"負例「{name}」を期待した理由で拒否できません: {exc}")
            print(f"Negative: passed ({name})")
        else:
            fail(f"負例「{name}」を拒否できません")


def self_test(root: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="system-design-validator-") as temporary:
        fixture = Path(temporary) / "repository"
        shutil.copytree(
            root,
            fixture,
            ignore=shutil.ignore_patterns(".git", "__pycache__"),
            symlinks=True,
        )
        skills = fixture / "plugins/system-design/skills"
        for name in EXPECTED_SKILLS:
            directory = skills / name
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "SKILL.md").write_text(
                fixture_skill(name),
                encoding="utf-8",
            )
        validate_repository(fixture)

        def empty_skills(candidate: Path) -> None:
            for path in (
                candidate / "plugins/system-design/skills"
            ).glob("*/SKILL.md"):
                path.unlink()

        def mismatch_marketplace(candidate: Path) -> None:
            path = candidate / ".agents/plugins/marketplace.json"
            value = load_json(path, "fixture marketplace")
            value["plugins"][0]["version"] = "9.9.9"
            write_json(path, value)

        def missing_heading(candidate: Path) -> None:
            path = (
                candidate
                / "plugins/system-design/skills/discover-requirements/SKILL.md"
            )
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "## 停止条件",
                    "## 停止の説明",
                ),
                encoding="utf-8",
            )

        def unqualified_dependency(candidate: Path) -> None:
            path = (
                candidate
                / "plugins/system-design/skills/discover-requirements/playbook.yml"
            )
            path.write_text(
                "version: 2\nrequires:\n  - plugin: write-doc\nsteps: []\n",
                encoding="utf-8",
            )

        def external_skill_step(candidate: Path) -> None:
            path = (
                candidate
                / "plugins/system-design/skills/discover-requirements/playbook.yml"
            )
            path.write_text(
                "version: 2\n"
                "requires:\n"
                "  - {plugin: write-doc, marketplace: write-doc}\n"
                "steps:\n"
                "  - {id: write, skill: write-doc}\n",
                encoding="utf-8",
            )

        def missing_playbook(candidate: Path) -> None:
            path = candidate / "plugins/system-design/playbooks/system-design/discover-requirements/playbook.yml"
            path.unlink()

        def missing_grill_dependency(candidate: Path) -> None:
            path = candidate / "plugins/system-design/playbooks/system-design/discover-requirements/playbook.yml"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "  - {plugin: grill, marketplace: grill}\n", ""
                ), encoding="utf-8"
            )

        def internal_playbook_cycle(candidate: Path) -> None:
            path = candidate / "plugins/system-design/playbooks/system-design/discover-requirements/playbook.yml"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "steps:\n", "steps:\n  - {id: cycle, playbook: discover-workload-model, purpose: 循環候補, needs: [request], provides: [bad]}\n", 1
                ), encoding="utf-8"
            )

        def unresolved_document_skip(candidate: Path) -> None:
            path = candidate / "plugins/system-design/playbooks/system-design/discover-requirements/playbook.yml"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "provides: [requirements_document_path]}",
                    "provides: [requirements_document_path], when: verification_report.status == ready}",
                ), encoding="utf-8"
            )

        def wrong_document_type(candidate: Path) -> None:
            path = candidate / "plugins/system-design/playbooks/system-design/discover-requirements/playbook.yml"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "document_type: requirements-discovery",
                    "document_type: architecture",
                ),
                encoding="utf-8",
            )

        def missing_supply(candidate: Path) -> None:
            path = candidate / "plugins/system-design/playbooks/system-design/discover-requirements/playbook.yml"
            path.write_text(path.read_text(encoding="utf-8").replace(
                "provides: [grounded_input]", "provides: [discarded_ground]", 1
            ), encoding="utf-8")

        def unknown_need(candidate: Path) -> None:
            path = candidate / "plugins/system-design/playbooks/system-design/discover-requirements/playbook.yml"
            path.write_text(path.read_text(encoding="utf-8").replace(
                "needs: [grounded_input, material, open_questions]",
                "needs: [grounded_input, material, open_questions, unknown_input]", 1
            ), encoding="utf-8")

        def duplicate_supply(candidate: Path) -> None:
            path = candidate / "plugins/system-design/playbooks/system-design/discover-requirements/playbook.yml"
            path.write_text(path.read_text(encoding="utf-8").replace(
                "provides: [decisions, open_questions]",
                "provides: [decisions, open_questions, material]", 1
            ), encoding="utf-8")

        def forward_cycle(candidate: Path) -> None:
            path = candidate / "plugins/system-design/playbooks/system-design/discover-requirements/playbook.yml"
            path.write_text(path.read_text(encoding="utf-8").replace(
                "needs: [run_root, request, referenced_artifacts]",
                "needs: [run_root, request, referenced_artifacts, material]", 1
            ), encoding="utf-8")

        def missing_required_cli_need(candidate: Path) -> None:
            path = candidate / "plugins/system-design/playbooks/system-design/discover-workload-model/playbook.yml"
            path.write_text(path.read_text(encoding="utf-8").replace(
                "needs: [grounded_input, material, open_questions]",
                "needs: [material, open_questions]", 1
            ), encoding="utf-8")

        def missing_plan_cleanup_need(candidate: Path) -> None:
            path = candidate / "plugins/system-design/playbooks/system-design/discover-workload-model/playbook.yml"
            path.write_text(path.read_text(encoding="utf-8").replace(
                "needs: [run_root], provides: [cleanup_manifest]",
                "needs: [], provides: [cleanup_manifest]", 1
            ), encoding="utf-8")

        def missing_ground_need(candidate: Path) -> None:
            path = candidate / "plugins/system-design/playbooks/system-design/discover-workload-model/playbook.yml"
            path.write_text(path.read_text(encoding="utf-8").replace(
                "needs: [request, referenced_artifacts, decisions, open_questions]",
                "needs: [referenced_artifacts, decisions, open_questions]", 1
            ), encoding="utf-8")

        def missing_material_need(candidate: Path) -> None:
            path = candidate / "plugins/system-design/playbooks/system-design/discover-workload-model/playbook.yml"
            path.write_text(path.read_text(encoding="utf-8").replace(
                "needs: [grounded_input, workload_artifact]",
                "needs: [grounded_input]", 1
            ), encoding="utf-8")

        def missing_cleanup_need(candidate: Path) -> None:
            path = candidate / "plugins/system-design/playbooks/system-design/discover-workload-model/playbook.yml"
            path.write_text(path.read_text(encoding="utf-8").replace(
                "needs: [cleanup_manifest], provides: [cleanup_report]",
                "needs: [], provides: [cleanup_report]", 1
            ), encoding="utf-8")

        def missing_finalize_cleanup_need(candidate: Path) -> None:
            path = candidate / "plugins/system-design/playbooks/system-design/design-cloud-architecture/playbook.yml"
            path.write_text(path.read_text(encoding="utf-8").replace(
                "needs: [cleanup_manifest], provides: [cleanup_report]",
                "needs: [], provides: [cleanup_report]", 1
            ), encoding="utf-8")

        def composition_term_in_skill(candidate: Path) -> None:
            path = candidate / "plugins/system-design/skills/discover-requirements/SKILL.md"
            path.write_text(path.read_text(encoding="utf-8") + "\n公開playbookを前提にする。\n", encoding="utf-8")

        def japanese_composition_term_in_reference(candidate: Path) -> None:
            path = candidate / "plugins/system-design/skills/discover-requirements/references/requirements-contract.md"
            path.write_text(path.read_text(encoding="utf-8") + "\nプレイブック工程を前提にする。\n", encoding="utf-8")

        def sibling_skill_name(candidate: Path) -> None:
            path = candidate / "plugins/system-design/skills/discover-workload-model/SKILL.md"
            path.write_text(path.read_text(encoding="utf-8") + "\ndiscover-quality-requirementsを先に使う。\n", encoding="utf-8")

        expect_rejected(fixture, "空の公開skill集合", "公開skill集合", empty_skills)
        expect_rejected(
            fixture,
            "runtime metadata不一致",
            "marketplace metadata",
            mismatch_marketplace,
        )
        expect_rejected(fixture, "必須契約節不足", "必須節", missing_heading)
        expect_rejected(
            fixture,
            "非修飾外部依存",
            "pluginとmarketplace",
            unqualified_dependency,
        )
        expect_rejected(
            fixture,
            "外部packageのskill参照",
            "skill/plugin工程",
            external_skill_step,
        )
        expect_rejected(fixture, "公開playbook不足", "公開playbook集合", missing_playbook)
        expect_rejected(fixture, "grill公開依存不足", "plugin: grill", missing_grill_dependency)
        expect_rejected(fixture, "playbook循環候補", "内部呼出し", internal_playbook_cycle)
        expect_rejected(fixture, "unresolved文書化skip", "documentをskip", unresolved_document_skip)
        expect_rejected(fixture, "専用文書型の不一致", "requirements-discovery", wrong_document_type)
        expect_rejected(fixture, "必須入力の供給欠落", "未知の必須入力", missing_supply)
        expect_rejected(fixture, "未知の必須入力参照", "未知の必須入力", unknown_need)
        expect_rejected(fixture, "成果の重複供給", "成果供給元が重複", duplicate_supply)
        expect_rejected(fixture, "前方参照cycle", "前方参照cycle", forward_cycle)
        expect_rejected(
            fixture,
            "verify必須CLI入力とneedsの不一致",
            "必須CLI入力がneedsにありません",
            missing_required_cli_need,
        )
        for label, mutate in (
            ("plan-cleanup必須CLI入力とneedsの不一致", missing_plan_cleanup_need),
            ("ground必須CLI入力とneedsの不一致", missing_ground_need),
            ("material必須CLI入力とneedsの不一致", missing_material_need),
            ("cleanup必須CLI入力とneedsの不一致", missing_cleanup_need),
            ("finalize必須入力とneedsの不一致", missing_finalize_cleanup_need),
        ):
            expect_rejected(
                fixture,
                label,
                "必須CLI入力がneedsにありません",
                mutate,
            )
        expect_rejected(
            fixture,
            "内部skillの英語構成単位",
            "構成単位への言及",
            composition_term_in_skill,
        )
        expect_rejected(
            fixture,
            "内部referenceの日本語構成単位",
            "構成単位への言及",
            japanese_composition_term_in_reference,
        )
        expect_rejected(
            fixture,
            "内部skillの兄弟名参照",
            "兄弟skill名",
            sibling_skill_name,
        )
    print("Validator self-test: passed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("root")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root)
    try:
        self_test(root) if args.self_test else validate_repository(root)
    except (OSError, UnicodeError, ValidationError) as exc:
        print(f"FAIL: {exc}", file=os.sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
