#!/usr/bin/env python3
"""公開playbookで一責務成果の状態をMarkdownとhandoffへ一貫して写す。"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REQUIRED_OUTPUTS = {
    "discover-requirements": (
        "schema_version", "artifact", "claims", "stakeholders", "purpose", "observations",
        "scope", "system_boundary", "constraints", "requirements", "hypotheses",
        "open_questions", "solution_inputs", "handoff",
    ),
    "discover-workload-model": (
        "schema_version", "artifact", "input_artifacts", "claims", "workload_items",
        "sensitivities", "open_questions", "handoff", "change_log",
    ),
    "discover-quality-requirements": (
        "schema_version", "artifact", "input_artifacts", "claims", "quality_requirements",
        "category_coverage", "workload_links", "conflicts", "open_questions", "handoff",
        "change_log",
    ),
    "design-cloud-architecture": (
        "schema_version", "artifact", "input_artifacts", "provider_resolution", "drivers",
        "constraints", "scope", "deployment_model", "alternatives", "selections", "adrs",
        "diagram", "failure_scenarios", "traceability", "verification_plan", "open_questions",
        "change_log",
    ),
}
SCHEMA_V2_OUTPUTS = {
    "discover-requirements": (
        "derived_requirements", "design_decisions", "scope_budget", "decision_history",
        "terminology",
        "interaction_catalog",
    ),
    "discover-workload-model": ("design_inputs", "terminology"),
    "design-cloud-architecture": ("terminology",),
}
READY_STATES = {
    "discover-requirements": "ready_for_downstream",
    "discover-workload-model": "ready_for_downstream",
    "discover-quality-requirements": "ready_for_architecture",
    "design-cloud-architecture": "ready_for_implementation_handoff",
}
LIST_OUTPUTS = {
    "requirements", "workload_items", "quality_requirements", "selections", "adrs",
    "traceability", "verification_plan", "open_questions", "derived_requirements",
    "design_decisions", "decision_history", "design_inputs",
}
CHECKER_SCRIPTS = {
    "discover-requirements": "requirements.py",
    "discover-workload-model": "workload.py",
    "discover-quality-requirements": "quality.py",
    "design-cloud-architecture": "architecture.py",
}


def stop(message: str) -> None:
    raise SystemExit(f"[error] {message}")


def load_object(path: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        stop(f"{label}を読めない: {exc}")
    if not isinstance(value, dict):
        stop(f"{label}はJSON objectでなければならない")
    return value


def validate_artifact(kind: str, artifact: dict[str, Any]) -> None:
    if kind not in REQUIRED_OUTPUTS:
        stop(f"未知のplaybook種別: {kind}")
    if not artifact:
        stop("一責務スキル成果が空である")
    required = set(REQUIRED_OUTPUTS[kind])
    versioned = set(SCHEMA_V2_OUTPUTS.get(kind, ()))
    if artifact.get("schema_version") == 2:
        required |= versioned
    missing = sorted(key for key in required if key not in artifact)
    if missing:
        stop(f"一責務スキルの必須成果が欠落: {', '.join(missing)}")
    extra = sorted(set(artifact) - required - versioned)
    if extra:
        stop(f"一責務スキル成果に未知のkeyがある: {', '.join(extra)}")
    metadata = artifact.get("artifact")
    if not isinstance(metadata, dict) or not isinstance(metadata.get("id"), str) or not metadata["id"]:
        stop("artifact.idが無い")
    if not isinstance(metadata.get("state"), str) or not metadata["state"]:
        stop("artifact.stateが無い")
    for key in LIST_OUTPUTS & set(artifact):
        if not isinstance(artifact[key], list):
            stop(f"{key}は配列でなければならない")
    if kind != "design-cloud-architecture":
        handoff = artifact.get("handoff")
        if not isinstance(handoff, dict) or type(handoff.get("ready")) is not bool:
            stop("一責務スキル成果のhandoff.readyが無い")
        blockers = handoff.get("blocking_question_ids")
        if not isinstance(blockers, list) or not all(isinstance(value, str) and value for value in blockers):
            stop("一責務スキル成果のblocking_question_idsが不正")


def validate_with_skill_checker(kind: str, artifact_path: str) -> None:
    script_name = CHECKER_SCRIPTS.get(kind)
    if script_name is None:
        stop(f"未知のplaybook種別: {kind}")
    package = Path(__file__).resolve().parent.parent
    checker = package / "skills" / kind / "scripts" / script_name
    result = subprocess.run(
        ["python3", str(checker), "check", "--file", artifact_path],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        reason = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        stop(f"一責務スキル成果が固有契約を満たさない: {reason}")


def normalized_question(item: dict[str, Any], source: str) -> dict[str, Any]:
    identifier = item.get("id")
    question = item.get("question")
    if not isinstance(identifier, str) or not identifier or not isinstance(question, str) or not question:
        stop(f"{source}の未決にid/questionが無い")
    return {
        "id": identifier,
        "question": question,
        "state": "open",
        "evidence_state": "unresolved",
        "source": source,
    }


def calculate_outcome(kind: str, grounded: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    validate_artifact(kind, artifact)
    ground_questions = []
    for item in grounded.get("open_questions", []):
        if not isinstance(item, dict):
            stop("grounded_inputのopen_questionsが不正")
        if item.get("state") == "open":
            ground_questions.append(normalized_question(item, "grill"))
    artifact_questions = []
    for item in artifact.get("open_questions", []):
        if not isinstance(item, dict):
            stop("一責務スキル成果のopen_questionsが不正")
        artifact_questions.append(normalized_question(item, "skill"))
    questions_by_id: dict[str, dict[str, Any]] = {}
    for item in [*ground_questions, *artifact_questions]:
        previous = questions_by_id.get(item["id"])
        if previous is not None and previous != item:
            stop(f"未決IDが異なる根拠から重複: {item['id']}")
        questions_by_id[item["id"]] = item

    metadata = artifact["artifact"]
    state = metadata["state"]
    artifact_ready = state == READY_STATES[kind]
    if kind == "design-cloud-architecture":
        artifact_blockers = [item["id"] for item in artifact_questions]
    else:
        artifact_handoff = artifact["handoff"]
        artifact_ready = artifact_ready and artifact_handoff["ready"]
        artifact_blockers = list(artifact_handoff["blocking_question_ids"])
    artifact_blockers = sorted(set(artifact_blockers) | {item["id"] for item in artifact_questions})
    if not artifact_ready and not artifact_blockers:
        state_id = f"ARTIFACT-STATE-{metadata['id']}"
        state_question = {
            "id": state_id,
            "question": f"一責務スキル成果の状態「{state}」を引き継ぎ可能にできるか",
            "state": "open",
            "evidence_state": "unresolved",
            "source": "artifact_state",
        }
        questions_by_id[state_id] = state_question
        artifact_blockers.append(state_id)
    blocked_by = sorted({item["id"] for item in ground_questions} | set(artifact_blockers))
    questions = list(questions_by_id.values())
    return {
        "status": "unresolved" if questions or not artifact_ready else "ready",
        "open_questions": questions,
        "artifact_state": state,
        "handoff": {"ready": artifact_ready and not blocked_by, "blocked_by": blocked_by},
    }


def build_material(kind: str, grounded_path: str, artifact_path: str, output_path: str) -> None:
    grounded = load_object(grounded_path, "grounded_input")
    artifact = load_object(artifact_path, "一責務スキル成果")
    validate_with_skill_checker(kind, artifact_path)
    outcome = calculate_outcome(kind, grounded, artifact)
    interaction_guidance = ""
    if kind == "discover-requirements":
        interaction_guidance = (
            "## 操作とイベント\n\n"
            "状態変更の意図をコマンド、読み取り専用操作をクエリ、各操作の成立事実をコマンドイベントと"
            "クエリイベントとして分ける。時間経過は時間イベント、内部処理の観測事実はシステムイベントとする。"
            "コマンドから状態変化を辿り、対操作、無変更、拒否、失敗の未決を省略しない。\n\n"
        )
    body = (
        "# 日本語の正本素材\n\n"
        "## 読み手と読後の判断\n\n"
        "読み手は、この正本を使って要求・設計の次の判断を行う開発担当者とサービス責任者である。"
        "読後は、確定情報と仮説・未決を区別し、根拠と追跡先から後続へ進めるか、誰へ何を確認するかを判断できる。\n\n"
        "## 正本の状態\n\n```json\n" + json.dumps(outcome, ensure_ascii=False, indent=2) + "\n```\n\n"
        "## 根拠状態\n\n決定と未決を区別し、未決を合意済みへ昇格させない。\n\n"
        "## 決定\n\n```json\n" + json.dumps(grounded.get("decisions", []), ensure_ascii=False, indent=2) + "\n```\n\n"
        "## 未決\n\n```json\n" + json.dumps(outcome["open_questions"], ensure_ascii=False, indent=2) + "\n```\n\n"
        + interaction_guidance
        + "## 一責務スキルの成果\n\n```json\n" + json.dumps(artifact, ensure_ascii=False, indent=2) + "\n```\n"
    )
    Path(output_path).write_text(body, encoding="utf-8")


def section_json(text: str, heading: str) -> Any:
    match = re.search(
        rf"^{re.escape(heading)}\s*\n\s*```json\s*\n(.*?)\n```",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        stop(f"materialの{heading} JSONが無い")
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        stop(f"materialの{heading} JSONが不正: {exc}")


def validate_provider(grounded: dict[str, Any], artifact: dict[str, Any]) -> None:
    ground = grounded.get("provider_resolution")
    actual = artifact.get("provider_resolution")
    required = {"provider", "resolved_config", "config_fingerprint"}
    if not isinstance(ground, dict) or not required <= set(ground):
        stop("同じ実行で解決したプロバイダー設定根拠が欠落")
    if not isinstance(actual, dict) or not required <= set(actual):
        stop("アーキテクチャ成果のプロバイダー設定根拠が欠落")
    for key in sorted(required):
        if ground[key] != actual[key]:
            stop(f"プロバイダー設定根拠が成果と不一致: {key}")


def verify_material(kind: str, grounded_path: str, material_path: str, output_path: str) -> None:
    grounded = load_object(grounded_path, "grounded_input")
    text = Path(material_path).read_text(encoding="utf-8")
    if not re.search(r"[ぁ-んァ-ヶ一-龯]", text):
        stop("materialが日本語ではない")
    for heading in ("## 正本の状態", "## 根拠状態", "## 決定", "## 未決", "## 一責務スキルの成果"):
        if heading not in text:
            stop("materialの必須節が無い")
    if kind == "discover-requirements" and "## 操作とイベント" not in text:
        stop("materialの操作とイベント節が無い")
    outcome = section_json(text, "## 正本の状態")
    artifact = section_json(text, "## 一責務スキルの成果")
    if not isinstance(artifact, dict):
        stop("material内の一責務スキル成果が不正")
    with tempfile.TemporaryDirectory(prefix="system-design-artifact-check-") as temporary:
        artifact_path = Path(temporary) / "artifact.json"
        artifact_path.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        validate_with_skill_checker(kind, str(artifact_path))
    expected = calculate_outcome(kind, grounded, artifact)
    if outcome != expected:
        stop("materialの状態・未決・handoffが入力成果と一致しない")
    for item in expected["open_questions"]:
        if item["question"] not in text:
            stop(f"未決がMarkdownに保持されていない: {item['id']}")
    if kind == "design-cloud-architecture":
        validate_provider(grounded, artifact)
    result = {
        "schema_version": 1,
        "status": expected["status"],
        "open_questions": expected["open_questions"],
        "artifact_state": expected["artifact_state"],
        "handoff": expected["handoff"],
        "checks": ["日本語", "根拠状態", "未決保持", "必須成果", "成果状態"],
    }
    if kind == "design-cloud-architecture":
        result["checks"].append("プロバイダー設定根拠")
    Path(output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
