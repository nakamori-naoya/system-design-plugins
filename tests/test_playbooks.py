#!/usr/bin/env python3
"""4公開playbookの状態伝播、設定同一性、依存、後片付けを実行検査する。"""
from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "plugins/system-design"
IDS = ("discover-requirements", "discover-workload-model", "discover-quality-requirements", "design-cloud-architecture")
DOCUMENT_TYPES = dict(zip(IDS, ("requirements-discovery", "workload-model", "quality-requirements", "cloud-architecture")))
DOCUMENT_NAMES = dict(zip(IDS, ("requirements-discovery.md", "workload-model.md", "quality-requirements.md", "cloud-architecture.md")))
ARTIFACT_FIXTURES = {identifier: ROOT / "tests/fixtures" / identifier / "success.json" for identifier in IDS}
SKILL_SCRIPTS = {
    "discover-requirements": "requirements.py", "discover-workload-model": "workload.py",
    "discover-quality-requirements": "quality.py", "design-cloud-architecture": "architecture.py",
}


def run(*args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if ok and result.returncode:
        raise AssertionError(f"失敗: {args}\n{result.stdout}\n{result.stderr}")
    if not ok and result.returncode == 0:
        raise AssertionError(f"拒否されなかった: {args}")
    return result


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def valid_artifact(identifier: str) -> dict:
    return json.loads(ARTIFACT_FIXTURES[identifier].read_text(encoding="utf-8"))


def unresolved_artifact(identifier: str) -> dict:
    value = valid_artifact(identifier)
    value["artifact"]["state"] = "saved_with_open_questions"
    if identifier == "discover-requirements":
        value["claims"].append({"id":"CLM-999","statement":"予約通知の経路は未合意","classification":"open_question","source":"要求確認会議","observed_at":"2026-09-14","owner":"サービス責任者"})
        value["open_questions"].append({"id":"OQ-999","question":"予約通知の経路を何にするか","claim_ids":["CLM-999"],"owner":"サービス責任者","affected_ids":["REQ-001"],"blocks":["quality"]})
        value["handoff"]["ready"] = False
        value["handoff"]["blocking_question_ids"] = ["OQ-999"]
    elif identifier == "discover-workload-model":
        value["open_questions"].append({"id":"OQ-WL-999","question":"予約ピーク率を再計測できるか","owner":"運用責任者","affected_refs":["WL-001.peak_rate"],"blocks":["cloud_design"]})
        metric = value["workload_items"][0]["characteristics"]["peak_rate"]
        metric.update({"status":"unresolved", "value":None, "confidence":"unknown", "open_question_ids":["OQ-WL-999"]})
        value["handoff"]["ready"] = False
        value["handoff"]["blocking_question_ids"] = ["OQ-WL-999"]
    elif identifier == "discover-quality-requirements":
        conflict = value["conflicts"][0]
        conflict.update({"status":"open", "resolution":None, "evidence_claim_ids":[], "open_question_ids":["OQ-QR-999"]})
        value["open_questions"].append({"id":"OQ-QR-999","question":"予約ピーク時の月額費用を再現できるか","owner":"費用責任者","affected_refs":["QR-006","QWL-004","QCON-001"],"blocks":["architecture"]})
        value["handoff"]["ready"] = False
        value["handoff"]["blocking_question_ids"] = ["OQ-QR-999"]
    else:
        value["open_questions"].append({"id":"OQ-ARCH-999","question":"通知経路を同期にするか非同期にするか","owner":"設計責任者","affected_refs":["SEL-003"],"blocks":["implementation"]})
    return value


def check_artifact(identifier: str, artifact_path: Path) -> None:
    script = PACKAGE / "skills" / identifier / "scripts" / SKILL_SCRIPTS[identifier]
    run("python3", str(script), "check", "--file", str(artifact_path))


def grounded_input(identifier: str, fixture_name: str, artifact: dict) -> dict:
    fixture = json.loads((ROOT / "tests/fixtures/playbooks" / f"{identifier}-{fixture_name}.json").read_text(encoding="utf-8"))
    incoming = {key: fixture[key] for key in ("request", "referenced_artifacts", "grill")}
    if identifier == "design-cloud-architecture":
        provider = artifact["provider_resolution"]
        incoming["provider_resolution"] = {
            "provider": provider["provider"], "config_source": "project",
            "selected_config": "/evidence/system-design.config.yml",
            "resolved_config": provider["resolved_config"],
            "config_fingerprint": provider["config_fingerprint"],
        }
    return incoming


def grill_yaml_roundtrip(temporary: Path, prefix: str, result: dict) -> dict:
    """公開YAMLの受渡しをfixtureで再現する。grillの実モデルは呼ばない。"""
    output = temporary / f"{prefix}-grill-output.yml"
    incoming = temporary / f"{prefix}-grill-input.yml"
    request = {
        "contract": "grill/grill", "version": 1, "topic": "予約サービスの対象範囲",
        "context": {"purpose": "次の設計へ渡す境界を確かめる", "audience": "サービス責任者", "boundary": "実装は変更しない"},
        "questions": [{"id": "q1", "question": "対象をどこまで含めるか", "recommendation": "目的を観測できるため利用者経路まで含める"}],
        "output_to": str(output),
    }
    def save_yaml(path, value):
        converted = subprocess.run(["yq", "-P", ".", "-"], input=json.dumps(value), text=True, capture_output=True, check=True)
        path.write_text(converted.stdout, encoding="utf-8")
    save_yaml(incoming, request)
    decoded = json.loads(run("yq", "-o=json", ".", str(incoming)).stdout)
    assert decoded == request
    save_yaml(output, dict(result, contract="grill/grill", version=1))
    received = json.loads(run("yq", "-o=json", ".", decoded["output_to"]).stdout)
    assert received == dict(result, contract="grill/grill", version=1)
    return received


def exercise_steps(playbook: Path, temporary: Path, fixture_name: str, artifact_mode: str = "ready") -> tuple[str, Path]:
    identifier = playbook.name
    incoming = temporary / f"{identifier}-{fixture_name}-{artifact_mode}-input.json"
    grounded = temporary / f"{identifier}-{fixture_name}-{artifact_mode}-grounded.json"
    artifact_path = temporary / f"{identifier}-{fixture_name}-{artifact_mode}-artifact.json"
    material = temporary / f"{identifier}-{fixture_name}-{artifact_mode}-material.md"
    report = temporary / f"{identifier}-{fixture_name}-{artifact_mode}-verify.json"
    artifact = unresolved_artifact(identifier) if artifact_mode == "unresolved" else valid_artifact(identifier)
    source = grounded_input(identifier, fixture_name, artifact)
    source["grill"] = grill_yaml_roundtrip(temporary, f"{identifier}-{fixture_name}-{artifact_mode}", source["grill"])
    write(incoming, source)
    write(artifact_path, artifact)
    check_artifact(identifier, artifact_path)
    scripts = playbook / "scripts"
    run("python3", str(scripts / "ground.py"), "--input", str(incoming), "--output", str(grounded))
    run("python3", str(scripts / "material.py"), "--grounded", str(grounded), "--artifact", str(artifact_path), "--output", str(material))
    run("python3", str(scripts / "verify.py"), "--grounded", str(grounded), "--material", str(material), "--output", str(report))
    result = json.loads(report.read_text(encoding="utf-8"))
    expected = "unresolved" if fixture_name == "unresolved" or artifact_mode == "unresolved" else "ready"
    assert result["status"] == expected
    assert result["handoff"]["ready"] is (expected == "ready")
    sources = {item["source"] for item in result["open_questions"]}
    if fixture_name == "unresolved": assert "grill" in sources
    if artifact_mode == "unresolved": assert "skill" in sources
    document = temporary / DOCUMENT_NAMES[identifier]
    document.write_text(material.read_text(encoding="utf-8"), encoding="utf-8")
    text = document.read_text(encoding="utf-8")
    assert document.name.isascii() and text.startswith("# 日本語の正本素材")
    assert f'"status": "{expected}"' in text
    if identifier == "discover-requirements":
        assert "## 操作とイベント" in text
        assert "コマンドイベントとクエリイベントとして分ける" in text
    return result["status"], document


def exercise_empty_artifact(playbook: Path, temporary: Path) -> None:
    incoming = temporary / f"{playbook.name}-empty-input.json"
    grounded = temporary / f"{playbook.name}-empty-grounded.json"
    empty = temporary / f"{playbook.name}-empty.json"
    output = temporary / f"{playbook.name}-must-not-exist.md"
    seed = valid_artifact(playbook.name)
    write(incoming, grounded_input(playbook.name, "normal", seed))
    write(empty, {})
    run("python3", str(playbook / "scripts/ground.py"), "--input", str(incoming), "--output", str(grounded))
    run("python3", str(playbook / "scripts/material.py"), "--grounded", str(grounded), "--artifact", str(empty), "--output", str(output), ok=False)
    assert not output.exists()


def exercise_missing_required_content(playbook: Path, temporary: Path) -> None:
    identifier = playbook.name
    missing_field = {
        "discover-requirements": "requirements",
        "discover-workload-model": "workload_items",
        "discover-quality-requirements": "quality_requirements",
        "design-cloud-architecture": "adrs",
    }[identifier]
    seed = valid_artifact(identifier)
    invalid = copy.deepcopy(seed)
    invalid[missing_field] = []
    incoming = temporary / f"{identifier}-missing-content-input.json"
    grounded = temporary / f"{identifier}-missing-content-grounded.json"
    artifact_path = temporary / f"{identifier}-missing-content-artifact.json"
    rejected_material = temporary / f"{identifier}-missing-content-rejected.md"
    write(incoming, grounded_input(identifier, "normal", seed))
    write(artifact_path, invalid)
    run("python3", str(playbook / "scripts/ground.py"), "--input", str(incoming), "--output", str(grounded))
    checker = PACKAGE / "skills" / identifier / "scripts" / SKILL_SCRIPTS[identifier]
    run("python3", str(checker), "check", "--file", str(artifact_path), ok=False)
    run(
        "python3", str(playbook / "scripts/material.py"),
        "--grounded", str(grounded), "--artifact", str(artifact_path),
        "--output", str(rejected_material), ok=False,
    )
    assert not rejected_material.exists()

    valid_path = temporary / f"{identifier}-valid-for-tamper.json"
    valid_material = temporary / f"{identifier}-valid-for-tamper.md"
    write(valid_path, seed)
    run(
        "python3", str(playbook / "scripts/material.py"),
        "--grounded", str(grounded), "--artifact", str(valid_path),
        "--output", str(valid_material),
    )
    pattern = re.compile(
        r"(## 一責務スキルの成果\s*\n\s*```json\s*\n).*?(\n```)",
        re.DOTALL,
    )
    tampered, count = pattern.subn(
        lambda match: match.group(1) + json.dumps(invalid, ensure_ascii=False, indent=2) + match.group(2),
        valid_material.read_text(encoding="utf-8"),
        count=1,
    )
    assert count == 1
    tampered_material = temporary / f"{identifier}-tampered-material.md"
    tampered_material.write_text(tampered, encoding="utf-8")
    report = temporary / f"{identifier}-tampered-report.json"
    run(
        "python3", str(playbook / "scripts/verify.py"),
        "--grounded", str(grounded), "--material", str(tampered_material),
        "--output", str(report), ok=False,
    )
    assert not report.exists()


def plan_and_cleanup(playbook: Path, root: Path, owned: list[Path], preserve: list[Path], ok: bool = True) -> dict:
    manifest = root / "manifest.json"
    report = root / "report.json"
    args = ["python3", str(playbook / "scripts/plan-cleanup.py"), "--run-root", str(root), "--output", str(manifest)]
    for path in owned: args += ["--owned", str(path)]
    for path in preserve: args += ["--preserve", str(path)]
    run(*args)
    run("python3", str(playbook / "scripts/cleanup.py"), "--manifest", str(manifest), "--output", str(report), ok=ok)
    return json.loads(report.read_text(encoding="utf-8"))


def exercise_cleanup(playbook: Path, temporary: Path) -> None:
    normal = temporary / "normal"; normal.mkdir()
    owned = normal / "owned.tmp"; owned.write_text("一時", encoding="utf-8")
    missing = normal / "already-deleted.tmp"
    keep = normal / "正本.md"; keep.write_text("正本", encoding="utf-8")
    report = plan_and_cleanup(playbook, normal, [owned, missing], [keep])
    assert report["status"] == "completed" and not owned.exists() and str(missing) in report["missing"] and keep.exists()

    outside = temporary.parent / f"outside-{playbook.name}.tmp"; outside.write_text("対象外", encoding="utf-8")
    for case in ("outside-first", "outside-last", "preserve-conflict", "symlink"):
        root = temporary / case; root.mkdir()
        first = root / "first.tmp"; first.write_text("残す", encoding="utf-8")
        target = root / "target.tmp"; target.write_text("残す", encoding="utf-8")
        link = root / "link.tmp"
        if case == "symlink": link.symlink_to(target)
        owned_paths = [outside, first] if case == "outside-first" else [first, outside] if case == "outside-last" else [first] if case == "preserve-conflict" else [link]
        preserve = [first] if case == "preserve-conflict" else []
        rejected = plan_and_cleanup(playbook, root, owned_paths, preserve, ok=False)
        assert rejected["status"] == "rejected" and rejected["deleted"] == [] and first.exists() and target.exists() and outside.exists()
    outside.unlink()


def provider_artifact(provider: str, resolution: dict) -> dict:
    value = valid_artifact("design-cloud-architecture")
    if provider == "gcp":
        value["deployment_model"]["provider_scope"] = ["gcp"]
        for alternative in value["alternatives"]:
            if alternative["deployment_mode"] != "multi_cloud":
                alternative["provider_scope"] = ["gcp"]
        for selection in value["selections"]:
            if selection["provider"] == "aws": selection["provider"] = "gcp"
        for boundary in value["diagram"]["boundaries"]:
            if boundary["provider"] == "aws": boundary["provider"] = "gcp"
    source_id = value["provider_resolution"]["source_artifact_id"]
    source = next(item for item in value["input_artifacts"] if item["id"] == source_id)
    source["locator"] = resolution["resolved_config"]
    source["version_or_hash"] = resolution["config_fingerprint"]
    value["provider_resolution"].update({
        "provider": provider, "resolved_config": resolution["resolved_config"],
        "config_fingerprint": resolution["config_fingerprint"],
    })
    return value


def exercise_provider(package: Path, temporary: Path) -> None:
    playbook = package / "playbooks/system-design/design-cloud-architecture"
    repo = temporary / "repo"; config_dir = repo / ".harness-plugins"; config_dir.mkdir(parents=True)
    prepare = playbook / "scripts/prepare.sh"
    resolved_by_provider = {}
    for provider in ("aws", "gcp"):
        (config_dir / "system-design.config.yml").write_text(f"version: 1\ncloud:\n  provider: {provider}\ninstructions:\n  architecture:\n    directive: 根拠から比較する\n", encoding="utf-8")
        prepared = run("bash", str(prepare), str(repo)).stdout.strip()
        resolution = json.loads(run("bash", str(playbook / "scripts/resolve.sh"), prepared).stdout)
        assert resolution["provider"] == provider and resolution["resolved_config"] == str(Path(prepared).resolve())
        assert resolution["config_fingerprint"].startswith("sha256:")
        resolved_by_provider[provider] = (prepared, resolution, provider_artifact(provider, resolution))
        grounded = temporary / f"{provider}-grounded.json"; artifact_path = temporary / f"{provider}-artifact.json"
        material = temporary / f"{provider}-material.md"; report = temporary / f"{provider}-report.json"
        write(grounded, {"schema_version":1,"status":"grounded","decisions":[],"open_questions":[],"provider_resolution":resolution})
        write(artifact_path, resolved_by_provider[provider][2]); check_artifact("design-cloud-architecture", artifact_path)
        run("python3", str(playbook / "scripts/material.py"), "--grounded", str(grounded), "--artifact", str(artifact_path), "--output", str(material))
        run("python3", str(playbook / "scripts/verify.py"), "--grounded", str(grounded), "--material", str(material), "--output", str(report))
        assert json.loads(report.read_text())["handoff"]["ready"] is True

    for ground_provider, artifact_provider in (("aws", "gcp"), ("gcp", "aws")):
        _, resolution, _ = resolved_by_provider[ground_provider]
        grounded = temporary / f"mismatch-{ground_provider}-{artifact_provider}.json"
        artifact_path = temporary / f"mismatch-{artifact_provider}.json"; material = temporary / f"mismatch-{ground_provider}-{artifact_provider}.md"
        write(grounded, {"schema_version":1,"status":"grounded","decisions":[],"open_questions":[],"provider_resolution":resolution})
        write(artifact_path, resolved_by_provider[artifact_provider][2])
        run("python3", str(playbook / "scripts/material.py"), "--grounded", str(grounded), "--artifact", str(artifact_path), "--output", str(material))
        run("python3", str(playbook / "scripts/verify.py"), "--grounded", str(grounded), "--material", str(material), "--output", str(temporary / "reject.json"), ok=False)
    missing = copy.deepcopy(resolved_by_provider["aws"][2]); missing["provider_resolution"].pop("config_fingerprint")
    grounded = temporary / "missing-ground.json"; artifact_path = temporary / "missing-artifact.json"; material = temporary / "missing.md"
    write(grounded, {"schema_version":1,"status":"grounded","decisions":[],"open_questions":[],"provider_resolution":resolved_by_provider["aws"][1]}); write(artifact_path, missing)
    run("python3", str(playbook / "scripts/material.py"), "--grounded", str(grounded), "--artifact", str(artifact_path), "--output", str(material), ok=False)
    assert not material.exists()
    for prepared, _, _ in resolved_by_provider.values(): run("bash", str(playbook / "scripts/finalize.sh"), prepared)
    (config_dir / "system-design.config.yml").write_text("version: 1\ncloud:\n  provider: aws\ninstructions:\n  architecture:\n    directive: 根拠から比較する\n", encoding="utf-8")
    prepared = run("bash", str(prepare), str(repo)).stdout.strip()
    final_root = temporary / "invalid-finalize"; final_root.mkdir()
    outside = temporary / "outside-owned.tmp"; outside.write_text("残す", encoding="utf-8")
    manifest = final_root / "manifest.json"; report = final_root / "report.json"
    write(manifest, {"run_root":str(final_root), "owned_files":[str(outside)], "preserve":[]})
    run("bash", str(playbook / "scripts/finalize.sh"), prepared, str(manifest), str(report), ok=False)
    assert Path(prepared).exists() and outside.exists() and json.loads(report.read_text())["deleted"] == []
    run("bash", str(playbook / "scripts/finalize.sh"), prepared)
    (config_dir / "system-design.config.yml").unlink()
    run("bash", str(prepare), str(repo), ok=False)
    assert json.loads(run("bash", str(playbook / "scripts/finalize.sh")).stdout)["provider_config"] == "未作成"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="system-design-playbooks-") as value:
        temporary = Path(value)
        for identifier in IDS:
            playbook = PACKAGE / "playbooks/system-design" / identifier
            contract = (playbook / "playbook.yml").read_text(encoding="utf-8")
            assert contract.count(f"document_type: {DOCUMENT_TYPES[identifier]}") == 2
            assert f"name: {DOCUMENT_NAMES[identifier]}" in contract
            if identifier != "design-cloud-architecture":
                assert json.loads(run("bash", str(playbook / "scripts/resolve.sh")).stdout)["skill"] == identifier
            exercise_steps(playbook, temporary, "normal", "ready")
            exercise_steps(playbook, temporary, "unresolved", "ready")
            exercise_steps(playbook, temporary, "normal", "unresolved")
            exercise_empty_artifact(playbook, temporary)
            exercise_missing_required_content(playbook, temporary)
            cleanup_root = temporary / f"cleanup-{identifier}"; cleanup_root.mkdir(); exercise_cleanup(playbook, cleanup_root)
        exercise_provider(PACKAGE, temporary / "provider")
        copied = temporary / "copied-system-design"; shutil.copytree(PACKAGE, copied)
        for identifier in IDS[:-1]:
            assert json.loads(run("bash", str(copied / "playbooks/system-design" / identifier / "scripts/resolve.sh")).stdout)["skill"] == identifier
        exercise_provider(copied, temporary / "copied-provider")
    print("Playbooks: passed (ready/grill未決/skill未決/空・必須内容欠落、設定同一性、安全cleanup、配布コピー)")


if __name__ == "__main__": main()
