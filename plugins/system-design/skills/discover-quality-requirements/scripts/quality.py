#!/usr/bin/env python3
"""Validate and safely persist a canonical quality-requirements artifact."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any


TOP_KEYS = {
    "schema_version",
    "artifact",
    "input_artifacts",
    "claims",
    "quality_requirements",
    "category_coverage",
    "workload_links",
    "conflicts",
    "open_questions",
    "handoff",
    "change_log",
}
CATEGORIES = {
    "latency",
    "throughput",
    "availability",
    "consistency",
    "durability",
    "recovery",
    "security",
    "privacy",
    "operability",
    "cost",
}
CLAIM_CLASSES = {"fact", "agreed_decision", "hypothesis"}
QR_STATES = {"agreed", "hypothesis", "unresolved"}
CONFIDENCE = {"high", "medium", "low", "unknown"}
OPERATORS = {"<", "<=", "=", ">=", ">"}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ContractError(ValueError):
    pass


def fail(message: str) -> None:
    raise ContractError(message)


def exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        fail(
            f"{label} keysが不正です: "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )


def as_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{label}はobjectでなければなりません")
    return value


def as_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        fail(f"{label}はarrayでなければなりません")
    return value


def nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{label}は非空文字列でなければなりません")
    return value


def optional_string(value: Any, label: str) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        fail(f"{label}はnullまたは非空文字列でなければなりません")


def string_list(value: Any, label: str, *, non_empty: bool = True) -> list[str]:
    items = as_list(value, label)
    if non_empty and not items:
        fail(f"{label}は1件以上必要です")
    if not all(isinstance(item, str) and item.strip() for item in items):
        fail(f"{label}は非空文字列のarrayでなければなりません")
    if len(set(items)) != len(items):
        fail(f"{label}に重複があります")
    return items


def ensure_refs(
    value: Any,
    allowed: set[str],
    label: str,
    *,
    non_empty: bool = True,
) -> list[str]:
    refs = string_list(value, label, non_empty=non_empty)
    missing = sorted(set(refs) - allowed)
    if missing:
        fail(f"{label}に未解決参照があります: {missing}")
    return refs


def register(identifier: Any, pattern: str, label: str, seen: dict[str, str]) -> str:
    value = nonempty(identifier, f"{label}.id")
    if re.fullmatch(pattern, value) is None:
        fail(f"{label}.idの形式が不正です: {value}")
    if value in seen:
        fail(f"IDが重複しています: {value} ({seen[value]}, {label})")
    seen[value] = label
    return value


def load(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        fail(f"artifactはregular fileでなければなりません: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"artifactが有効なUTF-8 JSONではありません: {exc}")
    return as_dict(value, "artifact root")


def number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail(f"{label}は数値でなければなりません")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0:
        fail(f"{label}は0以上の有限数でなければなりません")
    return numeric


def validate_metric(value: Any, label: str) -> None:
    metric = as_dict(value, label)
    exact_keys(metric, {"name", "statistic"}, label)
    nonempty(metric["name"], f"{label}.name")
    nonempty(metric["statistic"], f"{label}.statistic")


def validate_threshold(value: Any, label: str) -> None:
    threshold = as_dict(value, label)
    exact_keys(threshold, {"operator", "value", "unit"}, label)
    if threshold["operator"] not in OPERATORS:
        fail(f"{label}.operatorが不正です")
    number(threshold["value"], f"{label}.value")
    nonempty(threshold["unit"], f"{label}.unit")


def validate_payload(payload: dict[str, Any]) -> None:
    exact_keys(payload, TOP_KEYS, "top-level")
    if payload["schema_version"] != 1:
        fail("schema_versionは1でなければなりません")

    artifact = as_dict(payload["artifact"], "artifact")
    exact_keys(artifact, {"id", "version", "subject", "state"}, "artifact")
    artifact_id = nonempty(artifact["id"], "artifact.id")
    if re.fullmatch(r"QRMDL-[a-z0-9]+(?:-[a-z0-9]+)*", artifact_id) is None:
        fail("artifact.idの形式が不正です")
    if type(artifact["version"]) is not int or artifact["version"] < 1:
        fail("artifact.versionは1以上の整数でなければなりません")
    nonempty(artifact["subject"], "artifact.subject")
    if artifact["state"] not in {
        "ready_for_architecture",
        "saved_with_open_questions",
    }:
        fail("artifact.stateが不正です")

    seen: dict[str, str] = {artifact_id: "artifact"}
    source_ids: set[str] = set()
    source_kinds: dict[str, str] = {}
    input_keys = {"id", "kind", "locator", "version_or_hash", "observed_at"}
    inputs = as_list(payload["input_artifacts"], "input_artifacts")
    if not inputs:
        fail("input_artifactsは1件以上必要です")
    for index, raw in enumerate(inputs):
        item = as_dict(raw, f"input_artifacts[{index}]")
        exact_keys(item, input_keys, f"input_artifacts[{index}]")
        identifier = register(item["id"], r"SRC-[0-9]{3,}", "input artifact", seen)
        source_ids.add(identifier)
        if item["kind"] not in {
            "requirements",
            "journey",
            "domain",
            "workload",
            "telemetry",
            "decision",
            "other",
        }:
            fail(f"{identifier}.kindが不正です")
        source_kinds[identifier] = item["kind"]
        for key in ("locator", "version_or_hash", "observed_at"):
            nonempty(item[key], f"{identifier}.{key}")

    claim_classes: dict[str, str] = {}
    claim_categories: dict[str, str] = {}
    claim_keys = {
        "id",
        "statement",
        "classification",
        "source_artifact_id",
        "source_ref",
        "observed_at",
        "category",
    }
    claims = as_list(payload["claims"], "claims")
    if not claims:
        fail("claimsは1件以上必要です")
    for index, raw in enumerate(claims):
        item = as_dict(raw, f"claims[{index}]")
        exact_keys(item, claim_keys, f"claims[{index}]")
        identifier = register(item["id"], r"CLM-[0-9]{3,}", "claim", seen)
        nonempty(item["statement"], f"{identifier}.statement")
        if item["classification"] not in CLAIM_CLASSES:
            fail(f"{identifier}.classificationが不正です")
        if item["source_artifact_id"] not in source_ids:
            fail(f"{identifier}.source_artifact_idが未解決です")
        for key in ("source_ref", "observed_at"):
            nonempty(item[key], f"{identifier}.{key}")
        if item["category"] not in CATEGORIES:
            fail(f"{identifier}.categoryが不正です")
        claim_classes[identifier] = item["classification"]
        claim_categories[identifier] = item["category"]

    question_ids: set[str] = set()
    question_values = as_list(payload["open_questions"], "open_questions")
    question_keys = {"id", "question", "owner", "affected_refs", "blocks"}
    for index, raw in enumerate(question_values):
        item = as_dict(raw, f"open_questions[{index}]")
        exact_keys(item, question_keys, f"open_questions[{index}]")
        identifier = register(item["id"], r"OQ-QR-[0-9]{3,}", "open question", seen)
        question_ids.add(identifier)
        nonempty(item["question"], f"{identifier}.question")
        nonempty(item["owner"], f"{identifier}.owner")
        string_list(item["affected_refs"], f"{identifier}.affected_refs")
        string_list(item["blocks"], f"{identifier}.blocks")

    qr_keys = {
        "id",
        "category",
        "title",
        "status",
        "source_claim_ids",
        "upstream_refs",
        "workload_link_ids",
        "observation_point",
        "metric",
        "threshold",
        "time_window",
        "population",
        "verification_method",
        "verification_owner",
        "confidence",
        "design_sensitivity",
        "open_question_ids",
        "conflict_ids",
    }
    qr_values = as_list(payload["quality_requirements"], "quality_requirements")
    if not qr_values:
        fail("quality_requirementsは1件以上必要です")
    qr_ids: set[str] = set()
    for index, raw in enumerate(qr_values):
        item = as_dict(raw, f"quality_requirements[{index}]")
        exact_keys(item, qr_keys, f"quality_requirements[{index}]")
        qr_ids.add(register(item["id"], r"QR-[0-9]{3,}", "quality requirement", seen))

    link_keys = {
        "id",
        "quality_requirement_id",
        "workload_source_id",
        "workload_ref",
        "workload_status",
        "relation",
        "rationale",
        "conflict_ids",
        "open_question_ids",
    }
    link_values = as_list(payload["workload_links"], "workload_links")
    link_ids: set[str] = set()
    for index, raw in enumerate(link_values):
        item = as_dict(raw, f"workload_links[{index}]")
        exact_keys(item, link_keys, f"workload_links[{index}]")
        link_ids.add(register(item["id"], r"QWL-[0-9]{3,}", "workload link", seen))

    conflict_keys = {
        "id",
        "left_ref",
        "right_ref",
        "statement",
        "status",
        "resolution",
        "evidence_claim_ids",
        "open_question_ids",
    }
    conflict_values = as_list(payload["conflicts"], "conflicts")
    conflict_ids: set[str] = set()
    for index, raw in enumerate(conflict_values):
        item = as_dict(raw, f"conflicts[{index}]")
        exact_keys(item, conflict_keys, f"conflicts[{index}]")
        conflict_ids.add(register(item["id"], r"QCON-[0-9]{3,}", "conflict", seen))

    qr_categories: dict[str, str] = {}
    qr_states: dict[str, str] = {}
    for item in qr_values:
        identifier = item["id"]
        if item["category"] not in CATEGORIES:
            fail(f"{identifier}.categoryが不正です")
        category = item["category"]
        qr_categories[identifier] = category
        if item["status"] not in QR_STATES:
            fail(f"{identifier}.statusが不正です")
        status = item["status"]
        qr_states[identifier] = status
        nonempty(item["title"], f"{identifier}.title")
        claims_for_qr = ensure_refs(
            item["source_claim_ids"],
            set(claim_classes),
            f"{identifier}.source_claim_ids",
        )
        wrong_claims = [
            ref for ref in claims_for_qr if claim_categories[ref] != category
        ]
        if wrong_claims:
            fail(f"{identifier}が別categoryのclaimを参照しています: {wrong_claims}")
        string_list(item["upstream_refs"], f"{identifier}.upstream_refs")
        ensure_refs(
            item["workload_link_ids"],
            link_ids,
            f"{identifier}.workload_link_ids",
            non_empty=False,
        )
        questions = ensure_refs(
            item["open_question_ids"],
            question_ids,
            f"{identifier}.open_question_ids",
            non_empty=status == "unresolved",
        )
        ensure_refs(
            item["conflict_ids"],
            conflict_ids,
            f"{identifier}.conflict_ids",
            non_empty=False,
        )
        nonempty(item["design_sensitivity"], f"{identifier}.design_sensitivity")

        if status in {"agreed", "hypothesis"}:
            nonempty(item["observation_point"], f"{identifier}.observation_point")
            validate_metric(item["metric"], f"{identifier}.metric")
            validate_threshold(item["threshold"], f"{identifier}.threshold")
            for key in (
                "time_window",
                "population",
                "verification_method",
                "verification_owner",
            ):
                nonempty(item[key], f"{identifier}.{key}")
            if item["confidence"] not in CONFIDENCE - {"unknown"}:
                fail(f"{identifier}.confidenceに確からしさがありません")
            classes = {claim_classes[ref] for ref in claims_for_qr}
            if status == "agreed":
                if "agreed_decision" not in classes or "hypothesis" in classes:
                    fail(f"{identifier}に合意済み品質閾値の根拠がありません")
            elif "hypothesis" not in classes:
                fail(f"{identifier}にhypothesis claimがありません")
        else:
            optional_string(item["observation_point"], f"{identifier}.observation_point")
            if item["metric"] is not None:
                validate_metric(item["metric"], f"{identifier}.metric")
            if item["threshold"] is not None:
                fail(f"{identifier}.unresolvedはthreshold=nullでなければなりません")
            for key in (
                "time_window",
                "population",
                "verification_method",
                "verification_owner",
            ):
                optional_string(item[key], f"{identifier}.{key}")
            if item["confidence"] != "unknown" or not questions:
                fail(f"{identifier}.unresolvedはconfidence=unknownとopen questionが必要です")

    coverage_values = as_list(payload["category_coverage"], "category_coverage")
    coverage_keys = {
        "category",
        "disposition",
        "rationale",
        "quality_requirement_ids",
        "open_question_ids",
    }
    coverage_categories: set[str] = set()
    for index, raw in enumerate(coverage_values):
        item = as_dict(raw, f"category_coverage[{index}]")
        exact_keys(item, coverage_keys, f"category_coverage[{index}]")
        category = item["category"]
        if category not in CATEGORIES or category in coverage_categories:
            fail(f"category_coverage[{index}].categoryが不正または重複しています")
        coverage_categories.add(category)
        disposition = item["disposition"]
        if disposition not in {"specified", "unresolved", "not_applicable"}:
            fail(f"{category}.dispositionが不正です")
        nonempty(item["rationale"], f"{category}.rationale")
        refs = ensure_refs(
            item["quality_requirement_ids"],
            qr_ids,
            f"{category}.quality_requirement_ids",
            non_empty=disposition != "not_applicable",
        )
        if any(qr_categories[ref] != category for ref in refs):
            fail(f"{category}.quality_requirement_idsに別categoryがあります")
        questions = ensure_refs(
            item["open_question_ids"],
            question_ids,
            f"{category}.open_question_ids",
            non_empty=disposition == "unresolved",
        )
        if disposition == "specified" and any(qr_states[ref] == "unresolved" for ref in refs):
            fail(f"{category}.specifiedがunresolved QRを含んでいます")
        if disposition == "unresolved" and not any(
            qr_states[ref] == "unresolved" for ref in refs
        ):
            fail(f"{category}.unresolvedにunresolved QRがありません")
        if disposition == "not_applicable" and (refs or questions):
            fail(f"{category}.not_applicableにQRまたはopen questionを持てません")
    if coverage_categories != CATEGORIES:
        fail(
            "category_coverageが10 categoryと一致しません: "
            f"missing={sorted(CATEGORIES - coverage_categories)}"
        )

    links_by_qr: dict[str, set[str]] = {identifier: set() for identifier in qr_ids}
    for item in link_values:
        identifier = item["id"]
        qr_id = item["quality_requirement_id"]
        if qr_id not in qr_ids:
            fail(f"{identifier}.quality_requirement_idが未解決です")
        links_by_qr[qr_id].add(identifier)
        source_id = item["workload_source_id"]
        if source_id not in source_ids or source_kinds[source_id] != "workload":
            fail(f"{identifier}.workload_source_idがworkload artifactではありません")
        nonempty(item["workload_ref"], f"{identifier}.workload_ref")
        workload_status = item["workload_status"]
        if workload_status not in {
            "confirmed",
            "hypothesis",
            "unresolved",
            "not_applicable",
        }:
            fail(f"{identifier}.workload_statusが不正です")
        relation = item["relation"]
        if relation not in {"supports", "assumption", "conflicts", "blocked_by"}:
            fail(f"{identifier}.relationが不正です")
        nonempty(item["rationale"], f"{identifier}.rationale")
        link_conflicts = ensure_refs(
            item["conflict_ids"],
            conflict_ids,
            f"{identifier}.conflict_ids",
            non_empty=relation == "conflicts",
        )
        link_questions = ensure_refs(
            item["open_question_ids"],
            question_ids,
            f"{identifier}.open_question_ids",
            non_empty=relation == "blocked_by",
        )
        if relation == "supports" and workload_status != "confirmed":
            fail(f"{identifier}が未確認workloadをsupportsへ昇格しています")
        if relation == "assumption" and workload_status != "hypothesis":
            fail(f"{identifier}.assumptionはworkload hypothesisだけを参照できます")
        if workload_status == "hypothesis" and relation not in {"assumption", "conflicts"}:
            fail(f"{identifier}がworkload hypothesisの状態を保持していません")
        if workload_status == "unresolved" and relation not in {"blocked_by", "conflicts"}:
            fail(f"{identifier}がunresolved workloadを確定扱いしています")
        if relation != "conflicts" and link_conflicts:
            fail(f"{identifier}.conflict_idsはrelation=conflictsの場合だけ使用できます")
        if relation != "blocked_by" and link_questions:
            fail(f"{identifier}.open_question_idsはrelation=blocked_byの場合だけ使用できます")

    for item in qr_values:
        expected = links_by_qr[item["id"]]
        if set(item["workload_link_ids"]) != expected:
            fail(f"{item['id']}.workload_link_idsが逆参照と一致しません")

    open_conflicts: set[str] = set()
    conflict_refs = qr_ids | link_ids
    for item in conflict_values:
        identifier = item["id"]
        left = item["left_ref"]
        right = item["right_ref"]
        if left not in conflict_refs or right not in conflict_refs or left == right:
            fail(f"{identifier}.left_ref/right_refが不正です")
        nonempty(item["statement"], f"{identifier}.statement")
        if item["status"] not in {"open", "resolved"}:
            fail(f"{identifier}.statusが不正です")
        evidence = ensure_refs(
            item["evidence_claim_ids"],
            set(claim_classes),
            f"{identifier}.evidence_claim_ids",
            non_empty=item["status"] == "resolved",
        )
        questions = ensure_refs(
            item["open_question_ids"],
            question_ids,
            f"{identifier}.open_question_ids",
            non_empty=item["status"] == "open",
        )
        if item["status"] == "open":
            open_conflicts.add(identifier)
            if item["resolution"] is not None or evidence:
                fail(f"{identifier}.openはresolution/evidenceを持てません")
        else:
            nonempty(item["resolution"], f"{identifier}.resolution")
            if questions:
                fail(f"{identifier}.resolvedはopen questionを持てません")
            if any(claim_classes[ref] == "hypothesis" for ref in evidence):
                fail(f"{identifier}をhypothesisだけでresolvedにできません")

    for item in qr_values:
        for conflict_id in item["conflict_ids"]:
            conflict = next(value for value in conflict_values if value["id"] == conflict_id)
            if item["id"] not in {conflict["left_ref"], conflict["right_ref"]}:
                fail(f"{item['id']}.conflict_idsが逆参照と一致しません")
    for item in link_values:
        for conflict_id in item["conflict_ids"]:
            conflict = next(value for value in conflict_values if value["id"] == conflict_id)
            if item["id"] not in {conflict["left_ref"], conflict["right_ref"]}:
                fail(f"{item['id']}.conflict_idsが逆参照と一致しません")

    qr_by_id = {item["id"]: item for item in qr_values}
    link_by_id = {item["id"]: item for item in link_values}
    for conflict in conflict_values:
        for ref in (conflict["left_ref"], conflict["right_ref"]):
            target = qr_by_id.get(ref) or link_by_id.get(ref)
            if conflict["id"] not in target["conflict_ids"]:
                fail(f"{conflict['id']}が{ref}.conflict_idsから逆参照されていません")

    all_refs = qr_ids | link_ids | conflict_ids
    for item in question_values:
        ensure_refs(
            item["affected_refs"],
            all_refs,
            f"{item['id']}.affected_refs",
        )

    handoff = as_dict(payload["handoff"], "handoff")
    exact_keys(
        handoff,
        {
            "ready",
            "blocking_question_ids",
            "quality_requirement_ids",
            "workload_link_ids",
            "conflict_ids",
        },
        "handoff",
    )
    if type(handoff["ready"]) is not bool:
        fail("handoff.readyはbooleanでなければなりません")
    ready = handoff["ready"]
    blocking = ensure_refs(
        handoff["blocking_question_ids"],
        question_ids,
        "handoff.blocking_question_ids",
        non_empty=not ready,
    )
    if set(blocking) != question_ids:
        fail("handoff.blocking_question_idsがopen question集合と一致しません")
    if "workload" not in set(source_kinds.values()) and not question_ids:
        fail("workload modelがない場合は未決として保存しなければなりません")
    expected_ready = not question_ids and not open_conflicts
    if ready != expected_ready:
        fail("handoff.readyがopen question/conflict状態と一致しません")
    expected_state = "ready_for_architecture" if ready else "saved_with_open_questions"
    if artifact["state"] != expected_state:
        fail("artifact.stateとhandoff.readyが一致しません")
    expected_qrs = {identifier for identifier, state in qr_states.items() if state != "unresolved"}
    if set(ensure_refs(
        handoff["quality_requirement_ids"],
        qr_ids,
        "handoff.quality_requirement_ids",
        non_empty=False,
    )) != expected_qrs:
        fail("handoff.quality_requirement_idsが測定可能QR集合と一致しません")
    if set(ensure_refs(
        handoff["workload_link_ids"],
        link_ids,
        "handoff.workload_link_ids",
        non_empty=False,
    )) != link_ids:
        fail("handoff.workload_link_idsがworkload link集合と一致しません")
    if set(ensure_refs(
        handoff["conflict_ids"],
        conflict_ids,
        "handoff.conflict_ids",
        non_empty=False,
    )) != conflict_ids:
        fail("handoff.conflict_idsがconflict集合と一致しません")

    change_log = as_list(payload["change_log"], "change_log")
    if not change_log:
        fail("change_logは初版を含め1件以上必要です")
    versions: list[int] = []
    change_keys = {"version", "changed_input_ids", "invalidated_refs", "summary"}
    for index, raw in enumerate(change_log):
        item = as_dict(raw, f"change_log[{index}]")
        exact_keys(item, change_keys, f"change_log[{index}]")
        version = item["version"]
        if type(version) is not int or version < 1:
            fail(f"change_log[{index}].versionが不正です")
        versions.append(version)
        ensure_refs(
            item["changed_input_ids"],
            source_ids,
            f"change_log[{index}].changed_input_ids",
        )
        string_list(
            item["invalidated_refs"],
            f"change_log[{index}].invalidated_refs",
            non_empty=False,
        )
        nonempty(item["summary"], f"change_log[{index}].summary")
    if versions != list(range(1, artifact["version"] + 1)):
        fail("change_log.versionは1からartifact.versionまで連続しなければなりません")


def check_file(path: Path) -> dict[str, Any]:
    payload = load(path)
    validate_payload(payload)
    return payload


def safe_repo(raw: str) -> Path:
    repo = Path(raw)
    if not repo.is_absolute():
        fail("--repoは絶対pathでなければなりません")
    if repo.is_symlink() or not repo.is_dir():
        fail("--repoは実在するregular directoryでなければなりません")
    return repo.resolve(strict=True)


def write_artifact(
    repo: Path,
    slug: str,
    source: Path,
    expected_version: int | None,
) -> Path:
    if SLUG.fullmatch(slug) is None:
        fail("--slugはlower-case hyphen-caseでなければなりません")
    payload = check_file(source)
    target = repo / "system-design" / "quality-requirements" / f"{slug}.quality.json"
    current_path = repo
    for part in target.relative_to(repo).parts:
        current_path = current_path / part
        if current_path.exists() and current_path.is_symlink():
            fail(f"保存先のpathにsymlinkがあります: {current_path}")
    if target.exists():
        if expected_version is None:
            fail("既存正本を更新するには--expected-versionが必要です")
        current = check_file(target)
        version = current["artifact"]["version"]
        if version != expected_version:
            fail(
                "既存正本versionが期待値と一致しません: "
                f"expected={expected_version}, actual={version}"
            )
        if payload["artifact"]["id"] != current["artifact"]["id"]:
            fail("更新でartifact.idを変更できません")
        if payload["artifact"]["version"] != version + 1:
            fail("更新後artifact.versionは現在version+1でなければなりません")
    elif expected_version is not None:
        fail("初回保存に--expected-versionを指定できません")

    target.parent.mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{slug}.",
        suffix=".tmp",
        dir=target.parent,
        text=True,
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(canonical)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(
            temporary_path,
            stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH,
        )
        os.replace(temporary_path, target)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return target.resolve(strict=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check")
    check.add_argument("--file", required=True)
    write = subparsers.add_parser("write")
    write.add_argument("--repo", required=True)
    write.add_argument("--slug", required=True)
    write.add_argument("--file", required=True)
    write.add_argument("--expected-version", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        source = Path(args.file)
        if not source.is_absolute():
            fail("--fileは絶対pathでなければなりません")
        if args.command == "check":
            check_file(source)
            print(source.resolve(strict=True))
            return
        result = write_artifact(
            safe_repo(args.repo),
            args.slug,
            source,
            args.expected_version,
        )
        print(result)
    except (ContractError, OSError, UnicodeError) as exc:
        print(f"FAIL: {exc}", file=os.sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
