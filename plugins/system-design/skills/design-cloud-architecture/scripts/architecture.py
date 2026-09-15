#!/usr/bin/env python3
"""Validate and safely persist a canonical cloud architecture artifact."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any


TOP_KEYS_V1 = {
    "schema_version", "artifact", "input_artifacts", "provider_resolution", "drivers", "constraints",
    "scope", "deployment_model", "alternatives", "selections", "adrs", "diagram",
    "failure_scenarios", "traceability", "verification_plan", "open_questions",
    "change_log",
}
TOP_KEYS_V2 = TOP_KEYS_V1 | {"terminology"}
CAPABILITIES = {
    "provider", "region_az", "compute", "network", "storage", "database",
    "messaging", "identity", "edge", "observability", "backup_dr", "delivery",
}
DEPLOYMENT_MODES = {
    "single_cloud", "multi_cloud", "hybrid", "on_prem", "cloud_undecided",
}
PROVIDERS = {"aws", "gcp"}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ContractError(ValueError):
    pass


def fail(message: str) -> None:
    raise ContractError(message)


def as_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{label}はobjectでなければなりません")
    return value


def as_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        fail(f"{label}はarrayでなければなりません")
    return value


def exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        fail(
            f"{label} keysが不正です: "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )


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
        if any(re.search(r"[ぁ-んァ-ヶ一-龯]", term) is None for term in terms):
            fail(f"terminology.usages[{index}].preferred_termsは日本語の推奨用語名でなければなりません")


def ensure_refs(
    value: Any, allowed: set[str], label: str, *, non_empty: bool = True,
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


def validate_mode(mode: str, providers: list[str], label: str) -> None:
    if mode not in DEPLOYMENT_MODES:
        fail(f"{label}.modeが不正です")
    expected = {
        "single_cloud": len(providers) == 1,
        "multi_cloud": len(providers) >= 2,
        "hybrid": len(providers) >= 1,
        "on_prem": len(providers) == 0,
        "cloud_undecided": len(providers) == 0,
    }
    if not expected[mode]:
        fail(f"{label}.provider_scopeが{mode}の境界規則に一致しません")


def validate_payload(payload: dict[str, Any]) -> None:
    schema_version = payload.get("schema_version")
    if schema_version not in {1, 2}:
        fail("schema_versionは1または2でなければなりません")
    exact_keys(payload, TOP_KEYS_V1 if schema_version == 1 else TOP_KEYS_V2, "top-level")

    artifact = as_dict(payload["artifact"], "artifact")
    exact_keys(artifact, {"id", "version", "subject", "state"}, "artifact")
    artifact_id = nonempty(artifact["id"], "artifact.id")
    if re.fullmatch(r"ARCH-[a-z0-9]+(?:-[a-z0-9]+)*", artifact_id) is None:
        fail("artifact.idの形式が不正です")
    if type(artifact["version"]) is not int or artifact["version"] < 1:
        fail("artifact.versionは1以上の整数でなければなりません")
    nonempty(artifact["subject"], "artifact.subject")
    if artifact["state"] not in {
        "ready_for_implementation_handoff", "saved_with_open_questions",
    }:
        fail("artifact.stateが不正です")

    seen: dict[str, str] = {artifact_id: "artifact"}
    source_ids: set[str] = set()
    source_kinds: set[str] = set()
    source_kind_by_id: dict[str, str] = {}
    source_by_id: dict[str, dict[str, Any]] = {}
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
            "requirements_baseline", "logical_design", "workload", "quality",
            "organization", "operations", "budget", "compliance", "runtime_config",
            "terminology", "other",
        }:
            fail(f"{identifier}.kindが不正です")
        source_kinds.add(item["kind"])
        source_kind_by_id[identifier] = item["kind"]
        source_by_id[identifier] = item
        for key in ("locator", "version_or_hash", "observed_at"):
            nonempty(item[key], f"{identifier}.{key}")

    provider_resolution = as_dict(payload["provider_resolution"], "provider_resolution")
    exact_keys(
        provider_resolution,
        {"provider", "source_artifact_id", "resolved_config", "config_fingerprint"},
        "provider_resolution",
    )
    resolved_provider = provider_resolution["provider"]
    if resolved_provider not in PROVIDERS:
        fail("provider_resolution.providerはawsまたはgcpでなければなりません")
    provider_source_id = provider_resolution["source_artifact_id"]
    if source_kind_by_id.get(provider_source_id) != "runtime_config":
        fail("provider_resolution.source_artifact_idはruntime_config入力でなければなりません")
    resolved_config = nonempty(provider_resolution["resolved_config"], "provider_resolution.resolved_config")
    config_fingerprint = nonempty(provider_resolution["config_fingerprint"], "provider_resolution.config_fingerprint")
    if not config_fingerprint.startswith("sha256:"):
        fail("provider_resolution.config_fingerprintはsha256指紋でなければなりません")
    provider_source = source_by_id[provider_source_id]
    if provider_source["locator"] != resolved_config:
        fail("同じ実行の解決済み設定pathがruntime_config入力と一致しません")
    if provider_source["version_or_hash"] != config_fingerprint:
        fail("同じ実行の設定指紋がruntime_config入力と一致しません")

    driver_ids: set[str] = set()
    driver_kinds: dict[str, str] = {}
    driver_states: dict[str, str] = {}
    driver_keys = {
        "id", "kind", "upstream_ref", "source_artifact_id", "state", "statement",
        "observed_at", "impact",
    }
    drivers = as_list(payload["drivers"], "drivers")
    if not drivers:
        fail("driversは1件以上必要です")
    for index, raw in enumerate(drivers):
        item = as_dict(raw, f"drivers[{index}]")
        exact_keys(item, driver_keys, f"drivers[{index}]")
        identifier = register(item["id"], r"DRV-[0-9]{3,}", "driver", seen)
        driver_ids.add(identifier)
        if item["kind"] not in {"requirement", "quality", "workload"}:
            fail(f"{identifier}.kindが不正です")
        if item["state"] not in {"confirmed", "agreed", "hypothesis", "unresolved"}:
            fail(f"{identifier}.stateが不正です")
        if item["source_artifact_id"] not in source_ids:
            fail(f"{identifier}.source_artifact_idが未解決です")
        for key in ("upstream_ref", "statement", "observed_at", "impact"):
            nonempty(item[key], f"{identifier}.{key}")
        driver_kinds[identifier] = item["kind"]
        driver_states[identifier] = item["state"]
    for kind in ("requirement", "quality", "workload"):
        if kind not in set(driver_kinds.values()):
            fail(f"{kind} driverがありません")

    constraint_ids: set[str] = set()
    constraint_keys = {
        "id", "type", "statement", "classification", "source_artifact_id",
        "source_ref", "observed_at",
    }
    constraints = as_list(payload["constraints"], "constraints")
    if not constraints:
        fail("constraintsは1件以上必要です")
    for index, raw in enumerate(constraints):
        item = as_dict(raw, f"constraints[{index}]")
        exact_keys(item, constraint_keys, f"constraints[{index}]")
        identifier = register(item["id"], r"CON-[0-9]{3,}", "constraint", seen)
        constraint_ids.add(identifier)
        if item["type"] not in {
            "organization", "operations", "budget", "compliance", "location",
            "technical", "contract",
        }:
            fail(f"{identifier}.typeが不正です")
        if item["classification"] not in {"fact", "agreed_decision", "hypothesis"}:
            fail(f"{identifier}.classificationが不正です")
        if item["source_artifact_id"] not in source_ids:
            fail(f"{identifier}.source_artifact_idが未解決です")
        for key in ("statement", "source_ref", "observed_at"):
            nonempty(item[key], f"{identifier}.{key}")
    provider_constraint_ids = {
        item["id"]
        for item in constraints
        if item["source_artifact_id"] == provider_source_id
    }
    if not provider_constraint_ids:
        fail("解決providerがconstraintからruntime_config入力へ追跡されていません")

    scope = as_dict(payload["scope"], "scope")
    exact_keys(
        scope,
        {"system_boundary", "in_scope", "out_of_scope", "external_responsibilities"},
        "scope",
    )
    nonempty(scope["system_boundary"], "scope.system_boundary")
    for key in ("in_scope", "out_of_scope", "external_responsibilities"):
        string_list(scope[key], f"scope.{key}")

    question_ids: set[str] = set()
    question_keys = {"id", "question", "owner", "affected_refs", "blocks"}
    questions = as_list(payload["open_questions"], "open_questions")
    for index, raw in enumerate(questions):
        item = as_dict(raw, f"open_questions[{index}]")
        exact_keys(item, question_keys, f"open_questions[{index}]")
        identifier = register(item["id"], r"OQ-ARCH-[0-9]{3,}", "open question", seen)
        question_ids.add(identifier)
        nonempty(item["question"], f"{identifier}.question")
        nonempty(item["owner"], f"{identifier}.owner")
        string_list(item["affected_refs"], f"{identifier}.affected_refs")
        string_list(item["blocks"], f"{identifier}.blocks")

    alternative_keys = {
        "id", "name", "deployment_mode", "provider_scope", "driver_ids",
        "constraint_ids", "advantages", "disadvantages", "risks", "cost_effect",
        "operability_effect", "status", "rejection_reason",
    }
    alternatives = as_list(payload["alternatives"], "alternatives")
    if len(alternatives) < 2:
        fail("alternativesは比較のため2件以上必要です")
    alternative_ids: set[str] = set()
    for index, raw in enumerate(alternatives):
        item = as_dict(raw, f"alternatives[{index}]")
        exact_keys(item, alternative_keys, f"alternatives[{index}]")
        alternative_ids.add(register(item["id"], r"ALT-[0-9]{3,}", "alternative", seen))

    selection_keys = {
        "id", "category", "status", "choice", "provider", "service", "role",
        "requirement_driver_ids", "quality_driver_ids", "workload_driver_ids",
        "constraint_ids", "alternative_ids", "adr_ids", "verification_ids",
        "rationale", "open_question_ids",
    }
    selections = as_list(payload["selections"], "selections")
    selection_ids: set[str] = set()
    for index, raw in enumerate(selections):
        item = as_dict(raw, f"selections[{index}]")
        exact_keys(item, selection_keys, f"selections[{index}]")
        selection_ids.add(register(item["id"], r"SEL-[0-9]{3,}", "selection", seen))

    verification_keys = {
        "id", "kind", "objective", "method", "expected_evidence", "owner", "status",
        "evidence_refs", "trace_refs",
    }
    verifications = as_list(payload["verification_plan"], "verification_plan")
    if not verifications:
        fail("verification_planは1件以上必要です")
    verification_ids: set[str] = set()
    for index, raw in enumerate(verifications):
        item = as_dict(raw, f"verification_plan[{index}]")
        exact_keys(item, verification_keys, f"verification_plan[{index}]")
        verification_ids.add(register(item["id"], r"VER-[0-9]{3,}", "verification", seen))

    adr_keys = {
        "id", "status", "title", "context", "decision", "alternative_ids",
        "selection_ids", "driver_ids", "positive_consequences", "negative_consequences",
        "follow_ups", "verification_ids",
    }
    adrs = as_list(payload["adrs"], "adrs")
    if not adrs:
        fail("adrsは1件以上必要です")
    adr_ids: set[str] = set()
    for index, raw in enumerate(adrs):
        item = as_dict(raw, f"adrs[{index}]")
        exact_keys(item, adr_keys, f"adrs[{index}]")
        adr_ids.add(register(item["id"], r"ADR-[0-9]{3,}", "ADR", seen))

    for item in alternatives:
        identifier = item["id"]
        nonempty(item["name"], f"{identifier}.name")
        providers = string_list(
            item["provider_scope"], f"{identifier}.provider_scope", non_empty=False,
        )
        if set(providers) - PROVIDERS:
            fail(f"{identifier}.provider_scopeはawsまたはgcpだけを含められます")
        validate_mode(item["deployment_mode"], providers, identifier)
        ensure_refs(item["driver_ids"], driver_ids, f"{identifier}.driver_ids")
        ensure_refs(item["constraint_ids"], constraint_ids, f"{identifier}.constraint_ids")
        for key in ("advantages", "disadvantages", "risks"):
            string_list(item[key], f"{identifier}.{key}")
        nonempty(item["cost_effect"], f"{identifier}.cost_effect")
        nonempty(item["operability_effect"], f"{identifier}.operability_effect")
        if item["status"] not in {"chosen", "rejected", "deferred"}:
            fail(f"{identifier}.statusが不正です")
        if item["status"] == "chosen":
            if item["rejection_reason"] is not None:
                fail(f"{identifier}.chosenはrejection_reasonを持てません")
        else:
            nonempty(item["rejection_reason"], f"{identifier}.rejection_reason")

    deployment = as_dict(payload["deployment_model"], "deployment_model")
    exact_keys(
        deployment,
        {"mode", "provider_scope", "decision_state", "constraint_ids", "alternative_id", "open_question_ids"},
        "deployment_model",
    )
    providers = string_list(
        deployment["provider_scope"], "deployment_model.provider_scope", non_empty=False,
    )
    if set(providers) - PROVIDERS:
        fail("deployment_model.provider_scopeはawsまたはgcpだけを含められます")
    mode = deployment["mode"]
    validate_mode(mode, providers, "deployment_model")
    if mode in {"single_cloud", "multi_cloud", "hybrid"} and resolved_provider not in providers:
        fail("解決providerがdeployment_model.provider_scopeにありません")
    if deployment["decision_state"] not in {"decided", "proposed", "unresolved"}:
        fail("deployment_model.decision_stateが不正です")
    ensure_refs(deployment["constraint_ids"], constraint_ids, "deployment_model.constraint_ids")
    deployment_questions = ensure_refs(
        deployment["open_question_ids"], question_ids,
        "deployment_model.open_question_ids",
        non_empty=deployment["decision_state"] == "unresolved",
    )
    if mode == "cloud_undecided":
        if deployment["decision_state"] != "unresolved" or deployment["alternative_id"] is not None:
            fail("cloud_undecidedはunresolvedかつalternative未採用でなければなりません")
    else:
        if deployment["alternative_id"] not in alternative_ids:
            fail("deployment_model.alternative_idが未解決です")
    if deployment["decision_state"] != "unresolved" and deployment_questions:
        fail("決定済みdeployment_modelにopen questionを持てません")
    chosen = {item["id"] for item in alternatives if item["status"] == "chosen"}
    if deployment["decision_state"] == "decided":
        if chosen != {deployment["alternative_id"]}:
            fail("decided deployment modelはchosen alternative一件と一致しなければなりません")
    elif chosen:
        fail("未決またはproposed deployment modelにchosen alternativeを持てません")

    capability_seen: set[str] = set()
    selected_ids: set[str] = set()
    unresolved_ids: set[str] = set()
    selected_by_id: dict[str, dict[str, Any]] = {}
    for item in selections:
        identifier = item["id"]
        category = item["category"]
        if category not in CAPABILITIES or category in capability_seen:
            fail(f"{identifier}.categoryが不正または重複しています")
        capability_seen.add(category)
        if item["status"] not in {"selected", "unresolved", "not_applicable"}:
            fail(f"{identifier}.statusが不正です")
        status = item["status"]
        nonempty(item["rationale"], f"{identifier}.rationale")
        requirement_refs = ensure_refs(
            item["requirement_driver_ids"],
            {ref for ref in driver_ids if driver_kinds[ref] == "requirement"},
            f"{identifier}.requirement_driver_ids",
            non_empty=status == "selected",
        )
        quality_refs = ensure_refs(
            item["quality_driver_ids"],
            {ref for ref in driver_ids if driver_kinds[ref] == "quality"},
            f"{identifier}.quality_driver_ids",
            non_empty=status == "selected",
        )
        workload_refs = ensure_refs(
            item["workload_driver_ids"],
            {ref for ref in driver_ids if driver_kinds[ref] == "workload"},
            f"{identifier}.workload_driver_ids",
            non_empty=status == "selected",
        )
        constraint_refs = ensure_refs(
            item["constraint_ids"], constraint_ids, f"{identifier}.constraint_ids",
            non_empty=status == "selected",
        )
        alternative_refs = ensure_refs(
            item["alternative_ids"], alternative_ids, f"{identifier}.alternative_ids",
            non_empty=status == "selected",
        )
        adr_refs = ensure_refs(
            item["adr_ids"], adr_ids, f"{identifier}.adr_ids",
            non_empty=status == "selected",
        )
        verification_refs = ensure_refs(
            item["verification_ids"], verification_ids, f"{identifier}.verification_ids",
            non_empty=status == "selected",
        )
        open_refs = ensure_refs(
            item["open_question_ids"], question_ids, f"{identifier}.open_question_ids",
            non_empty=status == "unresolved",
        )
        if status == "selected":
            selected_ids.add(identifier)
            selected_by_id[identifier] = item
            if len(alternative_refs) < 2:
                fail(f"{identifier}.alternative_idsは比較のため2件以上必要です")
            for key in ("choice", "provider", "service", "role"):
                nonempty(item[key], f"{identifier}.{key}")
            if mode in {"single_cloud", "multi_cloud", "hybrid"} and item["provider"] != resolved_provider:
                fail(f"{identifier}.providerが解決providerと一致しません")
            if category == "provider" and not provider_constraint_ids.intersection(constraint_refs):
                fail(f"{identifier}がruntime_config由来のprovider constraintへ追跡されていません")
            grounded_drivers = set(requirement_refs) | set(quality_refs) | set(workload_refs)
            if any(driver_states[ref] == "unresolved" for ref in grounded_drivers):
                fail(f"{identifier}がunresolved driverをselected根拠にしています")
            if open_refs:
                fail(f"{identifier}.selectedはopen questionを持てません")
        elif status == "unresolved":
            unresolved_ids.add(identifier)
            for key in ("choice", "provider", "service"):
                if item[key] is not None:
                    fail(f"{identifier}.unresolvedの{key}はnullでなければなりません")
            optional_string(item["role"], f"{identifier}.role")
        else:
            for key in ("choice", "provider", "service"):
                if item[key] is not None:
                    fail(f"{identifier}.not_applicableの{key}はnullでなければなりません")
            optional_string(item["role"], f"{identifier}.role")
            if any((requirement_refs, quality_refs, workload_refs, constraint_refs, alternative_refs, adr_refs, verification_refs, open_refs)):
                fail(f"{identifier}.not_applicableに根拠・決定・未決参照を持てません")
    if capability_seen != CAPABILITIES:
        fail(f"selectionsが12 capabilityと一致しません: missing={sorted(CAPABILITIES - capability_seen)}")
    if mode == "cloud_undecided" and selected_ids:
        fail("cloud_undecidedでserviceをselectedにできません")

    for item in verifications:
        identifier = item["id"]
        if item["kind"] not in {
            "architecture_review", "load_test", "resilience_test", "security_review",
            "cost_model", "recovery_drill", "operability_drill",
        }:
            fail(f"{identifier}.kindが不正です")
        for key in ("objective", "method", "expected_evidence", "owner"):
            nonempty(item[key], f"{identifier}.{key}")
        if item["status"] not in {"planned", "passed", "failed"}:
            fail(f"{identifier}.statusが不正です")
        evidence = string_list(
            item["evidence_refs"], f"{identifier}.evidence_refs", non_empty=item["status"] != "planned",
        )
        if item["status"] == "planned" and evidence:
            fail(f"{identifier}.plannedは実施evidenceを持てません")
        string_list(item["trace_refs"], f"{identifier}.trace_refs")

    accepted_adrs: set[str] = set()
    for item in adrs:
        identifier = item["id"]
        if item["status"] not in {"accepted", "proposed", "superseded"}:
            fail(f"{identifier}.statusが不正です")
        if item["status"] == "accepted":
            accepted_adrs.add(identifier)
        for key in ("title", "context", "decision"):
            nonempty(item[key], f"{identifier}.{key}")
        adr_alternatives = ensure_refs(
            item["alternative_ids"], alternative_ids, f"{identifier}.alternative_ids"
        )
        if len(adr_alternatives) < 2:
            fail(f"{identifier}.alternative_idsは比較のため2件以上必要です")
        selection_refs = ensure_refs(item["selection_ids"], selection_ids, f"{identifier}.selection_ids")
        ensure_refs(item["driver_ids"], driver_ids, f"{identifier}.driver_ids")
        for key in ("positive_consequences", "negative_consequences", "follow_ups"):
            string_list(item[key], f"{identifier}.{key}")
        ensure_refs(item["verification_ids"], verification_ids, f"{identifier}.verification_ids")
        for selection_id in selection_refs:
            if identifier not in next(value for value in selections if value["id"] == selection_id)["adr_ids"]:
                fail(f"{identifier}.selection_idsがselectionから逆参照されていません")
    for selection_id, selection in selected_by_id.items():
        for adr_id in selection["adr_ids"]:
            adr = next(value for value in adrs if value["id"] == adr_id)
            if selection_id not in adr["selection_ids"]:
                fail(f"{selection_id}.adr_idsがADRから逆参照されていません")

    diagram = as_dict(payload["diagram"], "diagram")
    exact_keys(
        diagram,
        {"notation", "editable", "source", "boundaries", "nodes", "flows", "external_dependencies", "availability_units"},
        "diagram",
    )
    if diagram["notation"] != "mermaid" or diagram["editable"] is not True:
        fail("diagramはeditableなmermaidでなければなりません")
    mermaid = nonempty(diagram["source"], "diagram.source")
    if re.match(r"^\s*flowchart\s+(?:TB|TD|BT|RL|LR)\b", mermaid) is None:
        fail("diagram.sourceはMermaid flowchartで始めなければなりません")

    boundary_ids: set[str] = set()
    boundary_kinds: set[str] = set()
    boundary_envs: dict[str, str] = {}
    boundary_keys = {"id", "label", "kind", "environment", "provider", "parent_boundary_id"}
    boundaries = as_list(diagram["boundaries"], "diagram.boundaries")
    for index, raw in enumerate(boundaries):
        item = as_dict(raw, f"diagram.boundaries[{index}]")
        exact_keys(item, boundary_keys, f"diagram.boundaries[{index}]")
        identifier = register(item["id"], r"BND-[0-9]{3,}", "boundary", seen)
        boundary_ids.add(identifier)
        nonempty(item["label"], f"{identifier}.label")
        if item["kind"] not in {"system", "trust_zone", "external"}:
            fail(f"{identifier}.kindが不正です")
        if item["environment"] not in {"cloud", "on_prem", "external_party"}:
            fail(f"{identifier}.environmentが不正です")
        optional_string(item["provider"], f"{identifier}.provider")
        if item["provider"] is not None and item["provider"] not in PROVIDERS:
            fail(f"{identifier}.providerはawsまたはgcpでなければなりません")
        optional_string(item["parent_boundary_id"], f"{identifier}.parent_boundary_id")
        boundary_kinds.add(item["kind"])
        boundary_envs[identifier] = item["environment"]
    if boundary_kinds != {"system", "trust_zone", "external"}:
        fail("diagram.boundariesにsystem/trust_zone/externalが必要です")
    for item in boundaries:
        parent = item["parent_boundary_id"]
        if parent is not None and parent not in boundary_ids:
            fail(f"{item['id']}.parent_boundary_idが未解決です")
    boundary_providers = {item["provider"] for item in boundaries if item["provider"]}
    if mode in {"single_cloud", "multi_cloud", "hybrid"} and not set(providers) <= boundary_providers:
        fail("deployment providerがdiagram境界にありません")
    if mode == "hybrid" and "on_prem" not in set(boundary_envs.values()):
        fail("hybrid diagramにon-prem境界がありません")
    if mode == "on_prem" and "cloud" in set(boundary_envs.values()):
        fail("on_prem diagramにcloud境界を持てません")

    availability_ids: set[str] = set()
    availability_keys = {"id", "label", "node_ids", "failure_scope"}
    availability_values = as_list(diagram["availability_units"], "diagram.availability_units")
    if not availability_values:
        fail("diagram.availability_unitsは1件以上必要です")
    for index, raw in enumerate(availability_values):
        item = as_dict(raw, f"diagram.availability_units[{index}]")
        exact_keys(item, availability_keys, f"diagram.availability_units[{index}]")
        identifier = register(item["id"], r"AU-[0-9]{3,}", "availability unit", seen)
        availability_ids.add(identifier)
        nonempty(item["label"], f"{identifier}.label")
        string_list(item["node_ids"], f"{identifier}.node_ids")
        nonempty(item["failure_scope"], f"{identifier}.failure_scope")

    node_ids: set[str] = set()
    external_node_ids: set[str] = set()
    node_selections: set[str] = set()
    node_keys = {"id", "label", "kind", "selection_id", "boundary_id", "availability_unit_id"}
    nodes = as_list(diagram["nodes"], "diagram.nodes")
    if not nodes:
        fail("diagram.nodesは1件以上必要です")
    for index, raw in enumerate(nodes):
        item = as_dict(raw, f"diagram.nodes[{index}]")
        exact_keys(item, node_keys, f"diagram.nodes[{index}]")
        identifier = register(item["id"], r"NOD-[0-9]{3,}", "diagram node", seen)
        node_ids.add(identifier)
        nonempty(item["label"], f"{identifier}.label")
        if item["kind"] not in {"component", "candidate", "external"}:
            fail(f"{identifier}.kindが不正です")
        if item["boundary_id"] not in boundary_ids:
            fail(f"{identifier}.boundary_idが未解決です")
        if item["availability_unit_id"] not in availability_ids:
            fail(f"{identifier}.availability_unit_idが未解決です")
        if item["kind"] == "external":
            external_node_ids.add(identifier)
            if item["selection_id"] is not None:
                fail(f"{identifier}.externalはselectionを持てません")
        elif item["kind"] == "component":
            if item["selection_id"] not in selected_ids:
                fail(f"{identifier}.selection_idがselected capabilityではありません")
            node_selections.add(item["selection_id"])
        elif item["selection_id"] not in unresolved_ids:
            fail(f"{identifier}.candidateはunresolved selectionへ結ぶ必要があります")
    if node_selections != selected_ids:
        fail(f"selected capabilityがdiagram nodeへ全件追跡されていません: {sorted(selected_ids - node_selections)}")
    availability_node_refs: set[str] = set()
    for item in availability_values:
        refs = ensure_refs(item["node_ids"], node_ids, f"{item['id']}.node_ids")
        for ref in refs:
            if ref in availability_node_refs:
                fail(f"{ref}が複数availability unitに含まれています")
            availability_node_refs.add(ref)
            node = next(value for value in nodes if value["id"] == ref)
            if node["availability_unit_id"] != item["id"]:
                fail(f"{item['id']}.node_idsがnodeから逆参照されていません")
    if availability_node_refs != node_ids:
        fail(f"availability unitにnodeが不足しています: {sorted(node_ids - availability_node_refs)}")

    flow_ids: set[str] = set()
    synchrony: set[str] = set()
    crossing = False
    flow_keys = {
        "id", "from_node_id", "to_node_id", "data", "synchrony", "protocol",
        "trust_boundary_crossing", "failure_behavior",
    }
    flows = as_list(diagram["flows"], "diagram.flows")
    if not flows:
        fail("diagram.flowsは1件以上必要です")
    for index, raw in enumerate(flows):
        item = as_dict(raw, f"diagram.flows[{index}]")
        exact_keys(item, flow_keys, f"diagram.flows[{index}]")
        identifier = register(item["id"], r"FLW-[0-9]{3,}", "diagram flow", seen)
        flow_ids.add(identifier)
        if item["from_node_id"] not in node_ids or item["to_node_id"] not in node_ids:
            fail(f"{identifier}.from/to nodeが未解決です")
        for key in ("data", "protocol", "failure_behavior"):
            nonempty(item[key], f"{identifier}.{key}")
        if item["synchrony"] not in {"sync", "async"}:
            fail(f"{identifier}.synchronyが不正です")
        synchrony.add(item["synchrony"])
        if type(item["trust_boundary_crossing"]) is not bool:
            fail(f"{identifier}.trust_boundary_crossingはbooleanでなければなりません")
        from_node = next(value for value in nodes if value["id"] == item["from_node_id"])
        to_node = next(value for value in nodes if value["id"] == item["to_node_id"])
        if item["trust_boundary_crossing"] != (
            from_node["boundary_id"] != to_node["boundary_id"]
        ):
            fail(f"{identifier}.trust_boundary_crossingがnode境界と一致しません")
        crossing = crossing or item["trust_boundary_crossing"]
    if synchrony != {"sync", "async"}:
        fail("diagram.flowsにsyncとasyncが必要です")
    if not crossing:
        fail("diagram.flowsにtrust boundary crossingがありません")

    dependency_nodes: set[str] = set()
    dependency_keys = {"node_id", "owner", "contract_ref"}
    dependencies = as_list(diagram["external_dependencies"], "diagram.external_dependencies")
    if not dependencies:
        fail("diagram.external_dependenciesは1件以上必要です")
    for index, raw in enumerate(dependencies):
        item = as_dict(raw, f"diagram.external_dependencies[{index}]")
        exact_keys(item, dependency_keys, f"diagram.external_dependencies[{index}]")
        if item["node_id"] not in external_node_ids:
            fail(f"external_dependencies[{index}].node_idがexternal nodeではありません")
        dependency_nodes.add(item["node_id"])
        nonempty(item["owner"], f"external_dependencies[{index}].owner")
        nonempty(item["contract_ref"], f"external_dependencies[{index}].contract_ref")
    if dependency_nodes != external_node_ids:
        fail("external nodeがexternal_dependenciesへ全件追跡されていません")

    # コメント中のIDを表示証拠にせず、構造化要素と実際のMermaid要素を対応させる。
    rendered_subgraphs: dict[str, str] = {}
    rendered_subgraph_parents: dict[str, set[str]] = {}
    rendered_nodes: dict[str, tuple[set[str], str]] = {}
    rendered_edges: list[tuple[str, str, str]] = []
    stack: list[str] = []
    for raw_line in mermaid.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("%%"):
            continue
        subgraph_match = re.match(r'^subgraph\s+([A-Za-z][A-Za-z0-9_]*)\s*\["?([^\]]+)"?\]\s*$', line)
        if subgraph_match:
            alias, label = subgraph_match.groups()
            rendered_subgraphs[alias] = label
            rendered_subgraph_parents[alias] = set(stack)
            stack.append(alias)
            continue
        if line == "end":
            if not stack:
                fail("diagram.sourceのsubgraph endが対応していません")
            stack.pop()
            continue
        edge_match = re.match(
            r'^([A-Za-z][A-Za-z0-9_]*)\s*[-.=]+>\s*\|(.+?)\|\s*([A-Za-z][A-Za-z0-9_]*)\s*$',
            line,
        )
        if edge_match:
            rendered_edges.append((edge_match.group(1), edge_match.group(3), edge_match.group(2)))
            continue
        node_match = re.match(r'^([A-Za-z][A-Za-z0-9_]*)\s*[\[({]', line)
        if node_match:
            rendered_nodes[node_match.group(1)] = (set(stack), line)
    if stack:
        fail("diagram.sourceのsubgraphが閉じていません")

    for item in boundaries:
        alias = item["id"].replace("-", "")
        if item["id"] not in rendered_subgraphs.get(alias, ""):
            fail(f"diagram.sourceに表示境界がありません: {item['id']}")
        parent = item["parent_boundary_id"]
        if parent is not None and parent.replace("-", "") not in rendered_subgraph_parents[alias]:
            fail(f"diagram.sourceの表示境界階層が構造化定義と不一致: {item['id']}")
    for item in availability_values:
        alias = item["id"].replace("-", "")
        if item["id"] not in rendered_subgraphs.get(alias, ""):
            fail(f"diagram.sourceに表示可用性単位がありません: {item['id']}")
    for item in nodes:
        alias = item["id"].replace("-", "")
        rendered_node = rendered_nodes.get(alias)
        if rendered_node is None:
            fail(f"diagram.sourceに表示ノードがありません: {item['id']}")
        memberships, rendered_line = rendered_node
        if item["id"] not in rendered_line or re.search(r"[ぁ-んァ-ヶ一-龯]", rendered_line) is None:
            fail(f"diagram.sourceの表示ノードにIDと日本語表示名がありません: {item['id']}")
        expected = {
            item["boundary_id"].replace("-", ""),
            item["availability_unit_id"].replace("-", ""),
        }
        if not expected <= memberships:
            fail(f"diagram.sourceのノード所属境界が構造化定義と不一致: {item['id']}")
    for item in flows:
        source_alias = item["from_node_id"].replace("-", "")
        target_alias = item["to_node_id"].replace("-", "")
        matches = [label for source, target, label in rendered_edges
                   if source == source_alias and target == target_alias and item["id"] in label]
        if not matches:
            fail(f"diagram.sourceの表示フロー接続先が構造化定義と不一致: {item['id']}")
        label = matches[0]
        if item["synchrony"] == "sync" and ("同期" not in label or "非同期" in label):
            fail(f"diagram.sourceの表示フロー種別がsyncと不一致: {item['id']}")
        if item["synchrony"] == "async" and "非同期" not in label:
            fail(f"diagram.sourceの表示フロー種別がasyncと不一致: {item['id']}")

    failure_ids: set[str] = set()
    failure_keys = {
        "id", "trigger", "affected_availability_unit_ids", "affected_selection_ids",
        "detection", "degradation_behavior", "recovery", "requirement_driver_ids",
        "verification_ids",
    }
    failures = as_list(payload["failure_scenarios"], "failure_scenarios")
    if not failures:
        fail("failure_scenariosは1件以上必要です")
    for index, raw in enumerate(failures):
        item = as_dict(raw, f"failure_scenarios[{index}]")
        exact_keys(item, failure_keys, f"failure_scenarios[{index}]")
        identifier = register(item["id"], r"FAIL-[0-9]{3,}", "failure scenario", seen)
        failure_ids.add(identifier)
        for key in ("trigger", "detection", "degradation_behavior", "recovery"):
            nonempty(item[key], f"{identifier}.{key}")
        ensure_refs(item["affected_availability_unit_ids"], availability_ids, f"{identifier}.affected_availability_unit_ids")
        ensure_refs(item["affected_selection_ids"], selection_ids, f"{identifier}.affected_selection_ids")
        ensure_refs(
            item["requirement_driver_ids"],
            {ref for ref in driver_ids if driver_kinds[ref] == "requirement"},
            f"{identifier}.requirement_driver_ids",
        )
        ensure_refs(item["verification_ids"], verification_ids, f"{identifier}.verification_ids")

    trace_keys = {
        "selection_id", "requirement_driver_ids", "quality_driver_ids",
        "workload_driver_ids", "constraint_ids", "adr_ids", "verification_ids",
    }
    trace_values = as_list(payload["traceability"], "traceability")
    traced: set[str] = set()
    for index, raw in enumerate(trace_values):
        item = as_dict(raw, f"traceability[{index}]")
        exact_keys(item, trace_keys, f"traceability[{index}]")
        selection_id = item["selection_id"]
        if selection_id not in selected_ids or selection_id in traced:
            fail(f"traceability[{index}].selection_idが未解決または重複しています")
        traced.add(selection_id)
        selection = selected_by_id[selection_id]
        for key in (
            "requirement_driver_ids", "quality_driver_ids", "workload_driver_ids",
            "constraint_ids", "adr_ids", "verification_ids",
        ):
            refs = string_list(item[key], f"{selection_id}.traceability.{key}")
            if set(refs) != set(selection[key]):
                fail(f"{selection_id}.traceability.{key}がselectionと一致しません")
    if traced != selected_ids:
        fail(f"traceabilityにselected capabilityが不足しています: {sorted(selected_ids - traced)}")

    valid_question_refs = selection_ids | alternative_ids | adr_ids | verification_ids | failure_ids
    for item in questions:
        ensure_refs(item["affected_refs"], valid_question_refs, f"{item['id']}.affected_refs")

    for item in verifications:
        valid_trace_refs = selection_ids | alternative_ids | adr_ids | failure_ids | driver_ids | constraint_ids
        ensure_refs(item["trace_refs"], valid_trace_refs, f"{item['id']}.trace_refs")

    required_inputs = {"requirements_baseline", "logical_design", "workload", "quality"}
    missing_inputs = required_inputs - source_kinds
    ready = (
        not question_ids
        and deployment["decision_state"] == "decided"
        and not unresolved_ids
        and bool(accepted_adrs)
        and not missing_inputs
    )
    expected_state = "ready_for_implementation_handoff" if ready else "saved_with_open_questions"
    if artifact["state"] != expected_state:
        fail(
            "artifact.stateがinput/deployment/selection/ADR/open question状態と一致しません"
        )
    if artifact["state"] == "ready_for_implementation_handoff":
        if not any(
            driver_kinds[ref] == "requirement" and driver_states[ref] in {"confirmed", "agreed"}
            for ref in driver_ids
        ):
            fail("ready状態に確認済みrequirement driverがありません")
        if any(
            driver_states[ref] == "unresolved"
            for ref in driver_ids
            if driver_kinds[ref] in {"quality", "workload"}
        ):
            fail("ready状態にunresolved quality/workload driverがあります")

    if schema_version == 2:
        validate_terminology(payload["terminology"], set(seen))

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
        ensure_refs(item["changed_input_ids"], source_ids, f"change_log[{index}].changed_input_ids")
        string_list(item["invalidated_refs"], f"change_log[{index}].invalidated_refs", non_empty=False)
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


def write_artifact(repo: Path, slug: str, source: Path, expected_version: int | None) -> Path:
    if SLUG.fullmatch(slug) is None:
        fail("--slugはlower-case hyphen-caseでなければなりません")
    payload = check_file(source)
    target = repo / "system-design" / "architectures" / f"{slug}.architecture.json"
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
            fail(f"既存正本versionが期待値と一致しません: expected={expected_version}, actual={version}")
        if payload["artifact"]["id"] != current["artifact"]["id"]:
            fail("更新でartifact.idを変更できません")
        if payload["artifact"]["version"] != version + 1:
            fail("更新後artifact.versionは現在version+1でなければなりません")
    elif expected_version is not None:
        fail("初回保存に--expected-versionを指定できません")

    target.parent.mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{slug}.", suffix=".tmp", dir=target.parent, text=True,
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(canonical)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
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
        result = write_artifact(safe_repo(args.repo), args.slug, source, args.expected_version)
        print(result)
    except (ContractError, OSError, UnicodeError) as exc:
        print(f"FAIL: {exc}", file=os.sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
