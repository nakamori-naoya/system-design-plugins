#!/usr/bin/env python3
"""Validate and safely persist a usage/workload model canonical artifact."""

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
    "workload_items",
    "sensitivities",
    "open_questions",
    "question_review",
    "handoff",
    "change_log",
    "design_inputs",
    "terminology",
}
METRICS = {
    "population_size",
    "average_rate",
    "peak_rate",
    "burst_rate",
    "read_share",
    "write_share",
    "request_payload",
    "response_payload",
    "retention_period",
    "growth_rate",
    "fan_out",
    "hot_key_share",
}
CLAIM_CLASSES = {"fact", "agreed_decision", "hypothesis"}
CONFIRMED_CLASSES = {"fact", "agreed_decision"}
METRIC_STATES = {"confirmed", "hypothesis", "unresolved", "not_applicable"}
CONFIDENCE = {"high", "medium", "low", "unknown"}
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


def validate_terminology(raw: Any, known_ids: set[str]) -> None:
    terminology = as_dict(raw, "terminology")
    exact_keys(terminology, {"source", "usages"}, "terminology")
    source = as_dict(terminology["source"], "terminology.source")
    exact_keys(source, {"locator", "version"}, "terminology.source")
    nonempty(source["locator"], "terminology.source.locator")
    if type(source["version"]) is not int or source["version"] < 1:
        fail("terminology.source.versionは1以上の整数でなければなりません")
    subjects: set[str] = set()
    for index, raw_usage in enumerate(as_list(terminology["usages"], "terminology.usages")):
        usage = as_dict(raw_usage, f"terminology.usages[{index}]")
        exact_keys(usage, {"subject_id", "preferred_terms"}, f"terminology.usages[{index}]")
        subject_id = nonempty(usage["subject_id"], f"terminology.usages[{index}].subject_id")
        if subject_id not in known_ids:
            fail(f"terminology.usages[{index}].subject_idが未解決です: {subject_id}")
        if subject_id in subjects:
            fail(f"terminologyでsubject_idが重複しています: {subject_id}")
        subjects.add(subject_id)
        terms = string_list(usage["preferred_terms"], f"terminology.usages[{index}].preferred_terms")


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


def register(
    identifier: Any,
    pattern: str,
    label: str,
    seen: dict[str, str],
) -> str:
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


def validate_metric(
    raw: Any,
    metric_name: str,
    item_id: str,
    claim_classes: dict[str, str],
    claim_characteristics: dict[str, str],
    question_ids: set[str],
) -> dict[str, Any]:
    label = f"{item_id}.{metric_name}"
    metric = as_dict(raw, label)
    exact_keys(
        metric,
        {
            "status",
            "value",
            "unit",
            "time_window",
            "population",
            "claim_ids",
            "confidence",
            "calculation",
            "verification_plan",
            "sensitivity",
            "open_question_ids",
        },
        label,
    )
    status = metric["status"]
    if status not in METRIC_STATES:
        fail(f"{label}.statusが不正です")
    nonempty(metric["verification_plan"], f"{label}.verification_plan")
    nonempty(metric["sensitivity"], f"{label}.sensitivity")
    open_refs = ensure_refs(
        metric["open_question_ids"],
        question_ids,
        f"{label}.open_question_ids",
        non_empty=status == "unresolved",
    )
    claim_refs = ensure_refs(
        metric["claim_ids"],
        set(claim_classes),
        f"{label}.claim_ids",
        non_empty=status in {"confirmed", "hypothesis"},
    )
    wrong_claims = [
        ref
        for ref in claim_refs
        if claim_characteristics[ref] != metric_name
    ]
    if wrong_claims:
        fail(f"{label}が別characteristicのclaimを参照しています: {wrong_claims}")

    if status in {"confirmed", "hypothesis"}:
        number(metric["value"], f"{label}.value")
        nonempty(metric["unit"], f"{label}.unit")
        nonempty(metric["time_window"], f"{label}.time_window")
        nonempty(metric["population"], f"{label}.population")
        nonempty(metric["calculation"], f"{label}.calculation")
        if metric["confidence"] not in CONFIDENCE - {"unknown"}:
            fail(f"{label}.confidenceに確からしさがありません")
        classes = {claim_classes[ref] for ref in claim_refs}
        if status == "confirmed" and not classes <= CONFIRMED_CLASSES:
            fail(f"{label}がhypothesisをconfirmedへ昇格しています")
        if status == "hypothesis" and "hypothesis" not in classes:
            fail(f"{label}にhypothesis claimがありません")
    elif status == "unresolved":
        if metric["value"] is not None or metric["confidence"] != "unknown":
            fail(f"{label}.unresolvedはvalue=null、confidence=unknownでなければなりません")
        for key in ("unit", "time_window", "population", "calculation"):
            optional_string(metric[key], f"{label}.{key}")
        if not open_refs:
            fail(f"{label}.unresolvedにopen questionがありません")
    else:
        if (
            metric["value"] is not None
            or metric["confidence"] != "unknown"
            or claim_refs
            or open_refs
        ):
            fail(f"{label}.not_applicableに値、根拠、未決を持てません")
        for key in ("unit", "time_window", "population"):
            if metric[key] is not None:
                fail(f"{label}.not_applicableの{key}はnullでなければなりません")
        nonempty(metric["calculation"], f"{label}.calculation（非該当理由）")

    if metric_name in {"read_share", "write_share", "hot_key_share"} and metric["value"] is not None:
        if metric["unit"] != "fraction" or number(metric["value"], f"{label}.value") > 1:
            fail(f"{label}は0..1のfractionでなければなりません")
    return metric


def validate_distribution(
    raw: Any,
    item_id: str,
    claim_classes: dict[str, str],
    claim_characteristics: dict[str, str],
    question_ids: set[str],
) -> None:
    label = f"{item_id}.distribution"
    value = as_dict(raw, label)
    exact_keys(
        value,
        {
            "status",
            "shape",
            "skew_dimension",
            "summary",
            "claim_ids",
            "confidence",
            "verification_plan",
            "sensitivity",
            "open_question_ids",
        },
        label,
    )
    status = value["status"]
    if status not in {"confirmed", "hypothesis", "unresolved"}:
        fail(f"{label}.statusが不正です")
    nonempty(value["summary"], f"{label}.summary")
    nonempty(value["verification_plan"], f"{label}.verification_plan")
    nonempty(value["sensitivity"], f"{label}.sensitivity")
    claims = ensure_refs(
        value["claim_ids"],
        set(claim_classes),
        f"{label}.claim_ids",
        non_empty=status != "unresolved",
    )
    if any(claim_characteristics[ref] != "distribution" for ref in claims):
        fail(f"{label}がdistribution以外のclaimを参照しています")
    questions = ensure_refs(
        value["open_question_ids"],
        question_ids,
        f"{label}.open_question_ids",
        non_empty=status == "unresolved",
    )
    if status == "unresolved":
        if value["shape"] != "unknown" or value["confidence"] != "unknown":
            fail(f"{label}.unresolvedはshape/confidenceをunknownにしなければなりません")
        optional_string(value["skew_dimension"], f"{label}.skew_dimension")
        if not questions:
            fail(f"{label}.unresolvedにopen questionがありません")
        return
    if value["shape"] == "unknown":
        fail(f"{label}は根拠なしにunknown以外の状態を確定できません")
    nonempty(value["shape"], f"{label}.shape")
    nonempty(value["skew_dimension"], f"{label}.skew_dimension")
    if value["confidence"] not in CONFIDENCE - {"unknown"}:
        fail(f"{label}.confidenceに確からしさがありません")
    classes = {claim_classes[ref] for ref in claims}
    if status == "confirmed" and not classes <= CONFIRMED_CLASSES:
        fail(f"{label}がhypothesisをconfirmedへ昇格しています")
    if status == "hypothesis" and "hypothesis" not in classes:
        fail(f"{label}にhypothesis claimがありません")
    if value["shape"] == "uniform" and status != "confirmed":
        fail(f"{label}.shape=uniformは観測済みの場合だけ使用できます")


def validate_payload(payload: dict[str, Any]) -> None:
    schema_version = payload.get("schema_version")
    if schema_version != 2:
        fail("schema_versionは2でなければなりません")
    exact_keys(payload, TOP_KEYS, "top-level")

    artifact = as_dict(payload["artifact"], "artifact")
    exact_keys(artifact, {"id", "version", "subject", "state"}, "artifact")
    artifact_id = nonempty(artifact["id"], "artifact.id")
    if re.fullmatch(r"WLMDL-[a-z0-9]+(?:-[a-z0-9]+)*", artifact_id) is None:
        fail("artifact.idの形式が不正です")
    if type(artifact["version"]) is not int or artifact["version"] < 1:
        fail("artifact.versionは1以上の整数でなければなりません")
    nonempty(artifact["subject"], "artifact.subject")
    if artifact["state"] not in {"ready_for_downstream", "saved_with_open_questions"}:
        fail("artifact.stateが不正です")

    seen: dict[str, str] = {artifact_id: "artifact"}
    source_ids: set[str] = set()
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
            "telemetry",
            "forecast",
            "other",
        }:
            fail(f"{identifier}.kindが不正です")
        for key in ("locator", "version_or_hash", "observed_at"):
            nonempty(item[key], f"{identifier}.{key}")

    claim_classes: dict[str, str] = {}
    claim_characteristics: dict[str, str] = {}
    claim_keys = {
        "id",
        "statement",
        "classification",
        "source_artifact_id",
        "locator",
        "observed_at",
        "characteristic",
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
        for key in ("locator", "observed_at"):
            nonempty(item[key], f"{identifier}.{key}")
        characteristic = item["characteristic"]
        if characteristic not in METRICS | {"distribution"}:
            fail(f"{identifier}.characteristicが不正です")
        claim_classes[identifier] = item["classification"]
        claim_characteristics[identifier] = characteristic

    all_question_ids: set[str] = set()
    question_ids: set[str] = set()
    question_values = as_list(payload["open_questions"], "open_questions")
    question_keys = {"id", "question", "owner", "affected_refs", "blocks", "state", "resolution", "reason"}
    for index, raw in enumerate(question_values):
        item = as_dict(raw, f"open_questions[{index}]")
        exact_keys(item, question_keys, f"open_questions[{index}]")
        identifier = register(item["id"], r"OQ-WL-[0-9]{3,}", "open question", seen)
        all_question_ids.add(identifier)
        nonempty(item["question"], f"{identifier}.question")
        nonempty(item["owner"], f"{identifier}.owner")
        string_list(item["affected_refs"], f"{identifier}.affected_refs")
        string_list(item["blocks"], f"{identifier}.blocks")
        state = item["state"]
        if state not in {"open", "resolved", "withdrawn"}:
            fail(f"{identifier}.stateが不正です")
        if state == "resolved":
            nonempty(item["resolution"], f"{identifier}.resolution")
        elif item["resolution"] is not None:
            fail(f"{identifier}.resolutionはresolvedの場合だけ設定できます")
        nonempty(item["reason"], f"{identifier}.reason")
        if state == "open":
            question_ids.add(identifier)

    question_review = as_dict(payload["question_review"], "question_review")
    exact_keys(question_review, {"question_ids", "confirmed_by", "confirmation", "dialogue_complete"}, "question_review")
    reviewed = string_list(question_review["question_ids"], "question_review.question_ids", non_empty=False)
    if set(reviewed) != all_question_ids or len(reviewed) != len(all_question_ids):
        fail("question_review.question_idsが質問一覧全体と一致しません")
    nonempty(question_review["confirmed_by"], "question_review.confirmed_by")
    nonempty(question_review["confirmation"], "question_review.confirmation")
    if question_review["dialogue_complete"] is not True:
        fail("question_review.dialogue_completeは明示確認後のtrueでなければなりません")

    workload_ids: set[str] = set()
    workload_metric_refs: set[str] = set()
    workload_keys = {
        "id",
        "kind",
        "name",
        "period",
        "source_subject_refs",
        "characteristics",
        "distribution",
    }
    workloads = as_list(payload["workload_items"], "workload_items")
    if not workloads:
        fail("workload_itemsは1件以上必要です")
    for index, raw in enumerate(workloads):
        item = as_dict(raw, f"workload_items[{index}]")
        exact_keys(item, workload_keys, f"workload_items[{index}]")
        identifier = register(item["id"], r"WL-[0-9]{3,}", "workload item", seen)
        workload_ids.add(identifier)
        if item["kind"] not in {"actor", "action", "event"}:
            fail(f"{identifier}.kindが不正です")
        nonempty(item["name"], f"{identifier}.name")
        nonempty(item["period"], f"{identifier}.period")
        string_list(item["source_subject_refs"], f"{identifier}.source_subject_refs")
        characteristics = as_dict(item["characteristics"], f"{identifier}.characteristics")
        exact_keys(characteristics, METRICS, f"{identifier}.characteristics")
        validated: dict[str, dict[str, Any]] = {}
        for metric_name in sorted(METRICS):
            validated[metric_name] = validate_metric(
                characteristics[metric_name],
                metric_name,
                identifier,
                claim_classes,
                claim_characteristics,
                question_ids,
            )
            workload_metric_refs.add(f"{identifier}.{metric_name}")
        validate_distribution(
            item["distribution"],
            identifier,
            claim_classes,
            claim_characteristics,
            question_ids,
        )
        workload_metric_refs.add(f"{identifier}.distribution")
        read_metric = validated["read_share"]
        write_metric = validated["write_share"]
        valued = {"confirmed", "hypothesis"}
        if read_metric["status"] in valued and write_metric["status"] in valued:
            if (
                read_metric["time_window"] != write_metric["time_window"]
                or read_metric["population"] != write_metric["population"]
            ):
                fail(f"{identifier}のread/write比で時間窓または母集団が一致しません")
            total = float(read_metric["value"]) + float(write_metric["value"])
            if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
                fail(f"{identifier}のread/write fraction合計が1ではありません")

    for item in question_values:
        ensure_refs(
            item["affected_refs"],
            workload_metric_refs,
            f"{item['id']}.affected_refs",
        )

    sensitivity_ids: set[str] = set()
    sensitivity_keys = {
        "id",
        "workload_item_id",
        "characteristic",
        "condition",
        "affected_decision",
        "validation_trigger",
    }
    sensitivities = as_list(payload["sensitivities"], "sensitivities")
    if not sensitivities:
        fail("sensitivitiesは1件以上必要です")
    for index, raw in enumerate(sensitivities):
        item = as_dict(raw, f"sensitivities[{index}]")
        exact_keys(item, sensitivity_keys, f"sensitivities[{index}]")
        identifier = register(item["id"], r"SEN-[0-9]{3,}", "sensitivity", seen)
        sensitivity_ids.add(identifier)
        if item["workload_item_id"] not in workload_ids:
            fail(f"{identifier}.workload_item_idが未解決です")
        if item["characteristic"] not in METRICS | {"distribution"}:
            fail(f"{identifier}.characteristicが不正です")
        for key in ("condition", "affected_decision", "validation_trigger"):
            nonempty(item[key], f"{identifier}.{key}")

    design_input_ids: set[str] = set()
    if schema_version == 2:
        design_inputs = as_list(payload["design_inputs"], "design_inputs")
        if not design_inputs:
            fail("schema_version=2ではdesign_inputsが1件以上必要です")
        design_input_keys = {
            "id",
            "workload_refs",
            "source_claim_ids",
            "adopted_assumption",
            "applicability",
            "requirement_refs",
            "architecture_concerns",
            "confidence",
            "revisit_when",
            "out_of_scope",
        }
        workload_refs = workload_ids | workload_metric_refs | sensitivity_ids
        allowed_concerns = {
            "capacity",
            "partitioning",
            "asynchronous_processing",
            "flow_control",
            "retention_expiry",
            "failure_isolation",
        }
        for index, raw in enumerate(design_inputs):
            item = as_dict(raw, f"design_inputs[{index}]")
            exact_keys(item, design_input_keys, f"design_inputs[{index}]")
            identifier = register(item["id"], r"DIN-[0-9]{3,}", "design input", seen)
            design_input_ids.add(identifier)
            ensure_refs(item["workload_refs"], workload_refs, f"{identifier}.workload_refs")
            ensure_refs(item["source_claim_ids"], set(claim_classes), f"{identifier}.source_claim_ids")
            nonempty(item["adopted_assumption"], f"{identifier}.adopted_assumption")
            if item["applicability"] not in {
                "reference_scale",
                "implementation_acceptance",
                "localized_load",
            }:
                fail(f"{identifier}.applicabilityが不正です")
            string_list(item["requirement_refs"], f"{identifier}.requirement_refs")
            concerns = string_list(
                item["architecture_concerns"],
                f"{identifier}.architecture_concerns",
            )
            if not set(concerns) <= allowed_concerns:
                fail(f"{identifier}.architecture_concernsが不正です")
            if item["confidence"] not in CONFIDENCE - {"unknown"}:
                fail(f"{identifier}.confidenceが不正です")
            nonempty(item["revisit_when"], f"{identifier}.revisit_when")
            nonempty(item["out_of_scope"], f"{identifier}.out_of_scope")

        validate_terminology(payload["terminology"], set(seen))

    handoff = as_dict(payload["handoff"], "handoff")
    exact_keys(handoff, {"ready", "blocking_question_ids", "downstream"}, "handoff")
    if type(handoff["ready"]) is not bool:
        fail("handoff.readyはbooleanでなければなりません")
    ready = handoff["ready"]
    blocking = ensure_refs(
        handoff["blocking_question_ids"],
        question_ids,
        "handoff.blocking_question_ids",
        non_empty=not ready,
    )
    if ready and blocking:
        fail("handoff.ready=trueでblocking questionを持てません")
    expected_state = "ready_for_downstream" if ready else "saved_with_open_questions"
    if artifact["state"] != expected_state:
        fail("artifact.stateとhandoff.readyが一致しません")
    downstream = as_dict(handoff["downstream"], "handoff.downstream")
    exact_keys(downstream, {"quality", "cloud_design"}, "handoff.downstream")
    downstream_allowed = (
        workload_ids
        | workload_metric_refs
        | sensitivity_ids
        | design_input_ids
        | question_ids
    )
    for key in ("quality", "cloud_design"):
        ensure_refs(
            downstream[key],
            downstream_allowed,
            f"handoff.downstream.{key}",
            non_empty=False,
        )

    change_log = as_list(payload["change_log"], "change_log")
    if not change_log:
        fail("change_logは初版を含め1件以上必要です")
    versions: list[int] = []
    change_keys = {
        "version",
        "changed_input_ids",
        "invalidated_refs",
        "summary",
    }
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
    target = repo / "system-design" / "workloads" / f"{slug}.workload.json"
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
