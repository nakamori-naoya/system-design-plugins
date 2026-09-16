#!/usr/bin/env python3
"""Validate and safely persist a requirements-discovery canonical artifact."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any


TOP_KEYS = {
    "schema_version",
    "artifact",
    "claims",
    "stakeholders",
    "purpose",
    "observations",
    "scope",
    "system_boundary",
    "constraints",
    "requirements",
    "hypotheses",
    "open_questions",
    "question_review",
    "solution_inputs",
    "handoff",
    "derived_requirements",
    "design_decisions",
    "scope_budget",
    "decision_history",
    "terminology",
    "interaction_catalog",
}
CLAIM_CLASSES = {"fact", "agreed_decision", "hypothesis", "open_question"}
CONFIRMED_CLASSES = {"fact", "agreed_decision"}
DOWNSTREAM_KEYS = {"workload", "quality", "cloud_design"}
ID_PATTERNS = {
    "claim": re.compile(r"^CLM-[0-9]{3,}$"),
    "stakeholder": re.compile(r"^STK-[0-9]{3,}$"),
    "success observation": re.compile(r"^OBS-S-[0-9]{3,}$"),
    "failure observation": re.compile(r"^OBS-F-[0-9]{3,}$"),
    "in scope": re.compile(r"^SCP-I-[0-9]{3,}$"),
    "out of scope": re.compile(r"^SCP-O-[0-9]{3,}$"),
    "system responsibility": re.compile(r"^BND-S-[0-9]{3,}$"),
    "external party": re.compile(r"^BND-E-[0-9]{3,}$"),
    "constraint": re.compile(r"^CON-[0-9]{3,}$"),
    "requirement": re.compile(r"^REQ-[0-9]{3,}$"),
    "hypothesis": re.compile(r"^HYP-[0-9]{3,}$"),
    "open question": re.compile(r"^OQ-[0-9]{3,}$"),
    "solution input": re.compile(r"^HOW-[0-9]{3,}$"),
    "derived requirement": re.compile(r"^DRV-[0-9]{3,}$"),
    "design decision": re.compile(r"^DEC-[0-9]{3,}$"),
    "command": re.compile(r"^CMD-[0-9]{3,}$"),
    "query": re.compile(r"^QRY-[0-9]{3,}$"),
    "command event": re.compile(r"^CEVT-[0-9]{3,}$"),
    "query event": re.compile(r"^QEVT-[0-9]{3,}$"),
    "time event": re.compile(r"^TEVT-[0-9]{3,}$"),
    "system event": re.compile(r"^SEVT-[0-9]{3,}$"),
}
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


def bool_value(value: Any, label: str) -> bool:
    if type(value) is not bool:
        fail(f"{label}はbooleanでなければなりません")
    return value


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


def register_id(
    item: dict[str, Any],
    label: str,
    seen: dict[str, str],
) -> str:
    identifier = nonempty(item.get("id"), f"{label}.id")
    if ID_PATTERNS[label].fullmatch(identifier) is None:
        fail(f"{label}.idの形式が不正です: {identifier}")
    if identifier in seen:
        fail(f"IDが重複しています: {identifier} ({seen[identifier]}, {label})")
    seen[identifier] = label
    return identifier


def ensure_refs(
    raw: Any,
    allowed: set[str],
    label: str,
    *,
    non_empty: bool = True,
) -> list[str]:
    refs = string_list(raw, label, non_empty=non_empty)
    missing = sorted(set(refs) - allowed)
    if missing:
        fail(f"{label}に未解決参照があります: {missing}")
    return refs


def load(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        fail(f"artifactはregular fileでなければなりません: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"artifactが有効なUTF-8 JSONではありません: {exc}")
    return as_dict(payload, "artifact root")


def validate_claims(payload: dict[str, Any], seen: dict[str, str]) -> dict[str, str]:
    claims = as_list(payload["claims"], "claims")
    if not claims:
        fail("claimsは1件以上必要です")
    classifications: dict[str, str] = {}
    expected = {
        "id",
        "statement",
        "classification",
        "source",
        "observed_at",
        "owner",
    }
    for index, raw in enumerate(claims):
        item = as_dict(raw, f"claims[{index}]")
        exact_keys(item, expected, f"claims[{index}]")
        identifier = register_id(item, "claim", seen)
        for key in ("statement", "source", "observed_at", "owner"):
            nonempty(item[key], f"{identifier}.{key}")
        classification = item["classification"]
        if classification not in CLAIM_CLASSES:
            fail(f"{identifier}.classificationが不正です: {classification}")
        classifications[identifier] = classification
    return classifications


def validate_stakeholders(
    payload: dict[str, Any],
    claims: set[str],
    seen: dict[str, str],
) -> set[str]:
    values = as_list(payload["stakeholders"], "stakeholders")
    if not values:
        fail("stakeholdersは1件以上必要です")
    identifiers: set[str] = set()
    beneficiary_count = 0
    expected = {"id", "role", "relationship", "interest", "claim_ids"}
    for index, raw in enumerate(values):
        item = as_dict(raw, f"stakeholders[{index}]")
        exact_keys(item, expected, f"stakeholders[{index}]")
        identifier = register_id(item, "stakeholder", seen)
        identifiers.add(identifier)
        nonempty(item["role"], f"{identifier}.role")
        nonempty(item["interest"], f"{identifier}.interest")
        if item["relationship"] not in {"beneficiary", "stakeholder"}:
            fail(f"{identifier}.relationshipが不正です")
        beneficiary_count += item["relationship"] == "beneficiary"
        ensure_refs(item["claim_ids"], claims, f"{identifier}.claim_ids")
    if beneficiary_count == 0:
        fail("beneficiaryが1件以上必要です")
    return identifiers


def validate_named_items(
    raw_values: Any,
    label: str,
    claims: set[str],
    seen: dict[str, str],
) -> set[str]:
    values = as_list(raw_values, label)
    if not values:
        fail(f"{label}は1件以上必要です")
    identifiers: set[str] = set()
    expected = {"id", "statement", "claim_ids"}
    for index, raw in enumerate(values):
        item = as_dict(raw, f"{label}[{index}]")
        exact_keys(item, expected, f"{label}[{index}]")
        identifier = register_id(item, label, seen)
        identifiers.add(identifier)
        nonempty(item["statement"], f"{identifier}.statement")
        ensure_refs(item["claim_ids"], claims, f"{identifier}.claim_ids")
    return identifiers


def validate_observations(
    payload: dict[str, Any],
    claim_classes: dict[str, str],
    seen: dict[str, str],
) -> tuple[set[str], set[str], dict[str, str]]:
    observations = as_dict(payload["observations"], "observations")
    exact_keys(observations, {"success", "failure"}, "observations")
    all_ids: dict[str, str] = {}
    groups: list[tuple[str, str]] = [
        ("success", "success observation"),
        ("failure", "failure observation"),
    ]
    group_ids: dict[str, set[str]] = {"success": set(), "failure": set()}
    expected = {
        "id",
        "statement",
        "observer",
        "classification",
        "claim_ids",
        "verification_method",
    }
    for group, label in groups:
        values = as_list(observations[group], f"observations.{group}")
        if not values:
            fail(f"observations.{group}は1件以上必要です")
        for index, raw in enumerate(values):
            item = as_dict(raw, f"observations.{group}[{index}]")
            exact_keys(item, expected, f"observations.{group}[{index}]")
            identifier = register_id(item, label, seen)
            group_ids[group].add(identifier)
            nonempty(item["statement"], f"{identifier}.statement")
            nonempty(item["observer"], f"{identifier}.observer")
            nonempty(item["verification_method"], f"{identifier}.verification_method")
            classification = item["classification"]
            if classification not in CLAIM_CLASSES - {"open_question"}:
                fail(f"{identifier}.classificationが不正です")
            refs = ensure_refs(
                item["claim_ids"],
                set(claim_classes),
                f"{identifier}.claim_ids",
            )
            referenced_classes = {claim_classes[ref] for ref in refs}
            if classification in CONFIRMED_CLASSES and not referenced_classes <= CONFIRMED_CLASSES:
                fail(f"{identifier}がhypothesis/open_questionを確認済み観測へ昇格しています")
            if classification == "hypothesis" and "hypothesis" not in referenced_classes:
                fail(f"{identifier}のhypothesis根拠がありません")
            all_ids[identifier] = classification
    return group_ids["success"], group_ids["failure"], all_ids


def validate_payload(payload: dict[str, Any]) -> None:
    schema_version = payload.get("schema_version")
    if schema_version != 2:
        fail("schema_versionは2でなければなりません")
    exact_keys(payload, TOP_KEYS, "top-level")

    artifact = as_dict(payload["artifact"], "artifact")
    exact_keys(artifact, {"id", "version", "subject", "state"}, "artifact")
    artifact_id = nonempty(artifact["id"], "artifact.id")
    if re.fullmatch(r"REQDOC-[a-z0-9]+(?:-[a-z0-9]+)*", artifact_id) is None:
        fail("artifact.idの形式が不正です")
    if type(artifact["version"]) is not int or artifact["version"] < 1:
        fail("artifact.versionは1以上の整数でなければなりません")
    nonempty(artifact["subject"], "artifact.subject")
    if artifact["state"] not in {"ready_for_downstream", "saved_with_open_questions"}:
        fail("artifact.stateが不正です")

    seen: dict[str, str] = {artifact_id: "artifact"}
    claim_classes = validate_claims(payload, seen)
    claim_ids = set(claim_classes)
    stakeholder_ids = validate_stakeholders(payload, claim_ids, seen)

    purpose = as_dict(payload["purpose"], "purpose")
    exact_keys(
        purpose,
        {"beneficiary_ids", "problem", "desired_outcome", "claim_ids"},
        "purpose",
    )
    beneficiary_refs = ensure_refs(
        purpose["beneficiary_ids"],
        stakeholder_ids,
        "purpose.beneficiary_ids",
    )
    relationships = {
        item["id"]: item["relationship"]
        for item in payload["stakeholders"]
    }
    if any(relationships[ref] != "beneficiary" for ref in beneficiary_refs):
        fail("purpose.beneficiary_idsがbeneficiary以外を参照しています")
    nonempty(purpose["problem"], "purpose.problem")
    nonempty(purpose["desired_outcome"], "purpose.desired_outcome")
    ensure_refs(purpose["claim_ids"], claim_ids, "purpose.claim_ids")

    success_ids, _, observation_classes = validate_observations(
        payload,
        claim_classes,
        seen,
    )

    scope = as_dict(payload["scope"], "scope")
    exact_keys(scope, {"in", "out"}, "scope")
    in_scope = validate_named_items(
        scope["in"],
        "in scope",
        claim_ids,
        seen,
    )
    out_scope = validate_named_items(
        scope["out"],
        "out of scope",
        claim_ids,
        seen,
    )
    if {
        item["statement"].strip()
        for item in scope["in"]
    } & {
        item["statement"].strip()
        for item in scope["out"]
    }:
        fail("scope.inとscope.outに同じstatementがあります")

    boundary = as_dict(payload["system_boundary"], "system_boundary")
    exact_keys(
        boundary,
        {"responsibilities", "external_parties"},
        "system_boundary",
    )
    system_ids = validate_named_items(
        boundary["responsibilities"],
        "system responsibility",
        claim_ids,
        seen,
    )
    external_ids = validate_named_items(
        boundary["external_parties"],
        "external party",
        claim_ids,
        seen,
    )

    constraint_ids: set[str] = set()
    constraint_keys = {
        "id",
        "statement",
        "kind",
        "classification",
        "claim_ids",
        "verification_method",
        "impact",
    }
    for index, raw in enumerate(as_list(payload["constraints"], "constraints")):
        item = as_dict(raw, f"constraints[{index}]")
        exact_keys(item, constraint_keys, f"constraints[{index}]")
        identifier = register_id(item, "constraint", seen)
        constraint_ids.add(identifier)
        nonempty(item["statement"], f"{identifier}.statement")
        if item["kind"] not in {"business", "regulatory", "organizational", "technical"}:
            fail(f"{identifier}.kindが不正です")
        classification = item["classification"]
        if classification not in CONFIRMED_CLASSES:
            fail(f"{identifier}は未確認の制約をconstraintへ昇格しています")
        refs = ensure_refs(item["claim_ids"], claim_ids, f"{identifier}.claim_ids")
        if not {claim_classes[ref] for ref in refs} <= CONFIRMED_CLASSES:
            fail(f"{identifier}がhypothesis/open_questionをconstraintへ昇格しています")
        nonempty(item["verification_method"], f"{identifier}.verification_method")
        nonempty(item["impact"], f"{identifier}.impact")

    requirement_ids: set[str] = set()
    requirement_keys = {
        "id",
        "statement",
        "beneficiary_ids",
        "claim_ids",
        "success_observation_ids",
        "verification_method",
        "impact",
        "affects",
    }
    for index, raw in enumerate(as_list(payload["requirements"], "requirements")):
        item = as_dict(raw, f"requirements[{index}]")
        exact_keys(item, requirement_keys, f"requirements[{index}]")
        identifier = register_id(item, "requirement", seen)
        requirement_ids.add(identifier)
        nonempty(item["statement"], f"{identifier}.statement")
        beneficiary_refs = ensure_refs(
            item["beneficiary_ids"],
            stakeholder_ids,
            f"{identifier}.beneficiary_ids",
        )
        if any(relationships[ref] != "beneficiary" for ref in beneficiary_refs):
            fail(f"{identifier}.beneficiary_idsがbeneficiary以外を参照しています")
        refs = ensure_refs(item["claim_ids"], claim_ids, f"{identifier}.claim_ids")
        if not {claim_classes[ref] for ref in refs} <= CONFIRMED_CLASSES:
            fail(f"{identifier}がhypothesis/open_questionを要求へ昇格しています")
        observation_refs = ensure_refs(
            item["success_observation_ids"],
            success_ids,
            f"{identifier}.success_observation_ids",
        )
        if any(
            observation_classes[ref] != "agreed_decision"
            for ref in observation_refs
        ):
            fail(f"{identifier}が未合意の観測を受入条件へ昇格しています")
        nonempty(item["verification_method"], f"{identifier}.verification_method")
        impact = as_dict(item["impact"], f"{identifier}.impact")
        exact_keys(impact, {"if_met", "if_unmet"}, f"{identifier}.impact")
        nonempty(impact["if_met"], f"{identifier}.impact.if_met")
        nonempty(impact["if_unmet"], f"{identifier}.impact.if_unmet")
        affects = string_list(item["affects"], f"{identifier}.affects")
        if not set(affects) <= DOWNSTREAM_KEYS:
            fail(f"{identifier}.affectsに未知の後続関心があります")

    derived_requirement_ids: set[str] = set()
    design_decision_ids: set[str] = set()
    if schema_version == 2:
        derived_keys = {
            "id",
            "statement",
            "classification",
            "derived_from_claim_ids",
            "service_characteristic",
            "failure_risk",
            "required_outcome",
            "verification_method",
            "design_impacts",
            "revisit_when",
            "routed_to",
        }
        derived_values = as_list(
            payload["derived_requirements"],
            "derived_requirements",
        )
        if not derived_values:
            fail("schema_version=2ではderived_requirementsが1件以上必要です")
        for index, raw in enumerate(derived_values):
            item = as_dict(raw, f"derived_requirements[{index}]")
            exact_keys(item, derived_keys, f"derived_requirements[{index}]")
            identifier = register_id(item, "derived requirement", seen)
            derived_requirement_ids.add(identifier)
            for key in (
                "statement",
                "service_characteristic",
                "failure_risk",
                "required_outcome",
                "verification_method",
                "revisit_when",
            ):
                nonempty(item[key], f"{identifier}.{key}")
            classification = item["classification"]
            if classification not in {"confirmed", "hypothesis"}:
                fail(f"{identifier}.classificationが不正です")
            refs = ensure_refs(
                item["derived_from_claim_ids"],
                claim_ids,
                f"{identifier}.derived_from_claim_ids",
            )
            referenced_classes = {claim_classes[ref] for ref in refs}
            if classification == "confirmed" and not referenced_classes <= CONFIRMED_CLASSES:
                fail(f"{identifier}が未確認の根拠をconfirmedへ昇格しています")
            if classification == "hypothesis" and "hypothesis" not in referenced_classes:
                fail(f"{identifier}のhypothesis根拠がありません")
            string_list(item["design_impacts"], f"{identifier}.design_impacts")
            routes = string_list(item["routed_to"], f"{identifier}.routed_to")
            if not set(routes) <= DOWNSTREAM_KEYS:
                fail(f"{identifier}.routed_toに未知の後続関心があります")

        decision_keys = {
            "id",
            "statement",
            "basis",
            "claim_ids",
            "derived_requirement_ids",
            "rationale",
            "revisit_when",
            "routed_to",
        }
        for index, raw in enumerate(as_list(payload["design_decisions"], "design_decisions")):
            item = as_dict(raw, f"design_decisions[{index}]")
            exact_keys(item, decision_keys, f"design_decisions[{index}]")
            identifier = register_id(item, "design decision", seen)
            design_decision_ids.add(identifier)
            for key in ("statement", "rationale", "revisit_when"):
                nonempty(item[key], f"{identifier}.{key}")
            basis = item["basis"]
            if basis not in {"agreed_decision", "logically_required"}:
                fail(f"{identifier}.basisが不正です")
            refs = ensure_refs(item["claim_ids"], claim_ids, f"{identifier}.claim_ids")
            derived_refs = ensure_refs(
                item["derived_requirement_ids"],
                derived_requirement_ids,
                f"{identifier}.derived_requirement_ids",
                non_empty=basis == "logically_required",
            )
            if basis == "agreed_decision" and "agreed_decision" not in {
                claim_classes[ref] for ref in refs
            }:
                fail(f"{identifier}に合意済み決定の根拠がありません")
            if basis == "logically_required" and not derived_refs:
                fail(f"{identifier}に導出要件の根拠がありません")
            nonempty(item["routed_to"], f"{identifier}.routed_to")

        scope_budget = as_dict(payload["scope_budget"], "scope_budget")
        exact_keys(
            scope_budget,
            {
                "implementation_scope",
                "design_only_scope",
                "out_of_scope",
                "delivery_constraints",
            },
            "scope_budget",
        )
        for key in (
            "implementation_scope",
            "design_only_scope",
            "out_of_scope",
            "delivery_constraints",
        ):
            string_list(scope_budget[key], f"scope_budget.{key}", non_empty=False)
        # Deterministic validation declaration:
        # source=scope_budget contract (実装必須・設計説明のみ・対象外は排他);
        # input=the three scope lists; normalization=exact string comparison;
        # predicate=no item appears in more than one of the three lists;
        # diagnostic=the shared item and the lists it appears in;
        # positive=each item in exactly one list; negative=the same item in
        # implementation_scope and design_only_scope; boundary=an item in
        # delivery_constraints may repeat a scope item because it is a budget,
        # not a scope class. Whether an implementation item fits the budget is
        # semantic evaluation.
        scope_classes = ("implementation_scope", "design_only_scope", "out_of_scope")
        for left_index, left in enumerate(scope_classes):
            for right in scope_classes[left_index + 1:]:
                shared = set(scope_budget[left]) & set(scope_budget[right])
                if shared:
                    fail(f"scope_budgetの{left}と{right}に同じ項目があります: {sorted(shared)}")

        history = as_list(payload["decision_history"], "decision_history")
        if not history:
            fail("decision_historyは初版を含め1件以上必要です")
        versions: list[int] = []
        history_keys = {"version", "changed_claim_ids", "affected_ids", "summary"}
        history_allowed = (
            claim_ids
            | requirement_ids
            | derived_requirement_ids
            | design_decision_ids
            | constraint_ids
        )
        for index, raw in enumerate(history):
            item = as_dict(raw, f"decision_history[{index}]")
            exact_keys(item, history_keys, f"decision_history[{index}]")
            version = item["version"]
            if type(version) is not int or version < 1:
                fail(f"decision_history[{index}].versionが不正です")
            versions.append(version)
            ensure_refs(
                item["changed_claim_ids"],
                claim_ids,
                f"decision_history[{index}].changed_claim_ids",
            )
            ensure_refs(
                item["affected_ids"],
                history_allowed,
                f"decision_history[{index}].affected_ids",
                non_empty=False,
            )
            nonempty(item["summary"], f"decision_history[{index}].summary")
        if versions != list(range(1, artifact["version"] + 1)):
            fail("decision_history.versionは1からartifact.versionまで連続しなければなりません")

    hypothesis_ids: set[str] = set()
    hypothesis_keys = {
        "id",
        "statement",
        "claim_ids",
        "falsification_method",
        "affected_ids",
    }
    hypothesis_values = as_list(payload["hypotheses"], "hypotheses")
    for index, raw in enumerate(hypothesis_values):
        item = as_dict(raw, f"hypotheses[{index}]")
        exact_keys(item, hypothesis_keys, f"hypotheses[{index}]")
        identifier = register_id(item, "hypothesis", seen)
        hypothesis_ids.add(identifier)
        nonempty(item["statement"], f"{identifier}.statement")
        refs = ensure_refs(item["claim_ids"], claim_ids, f"{identifier}.claim_ids")
        if "hypothesis" not in {claim_classes[ref] for ref in refs}:
            fail(f"{identifier}にhypothesis claimがありません")
        nonempty(item["falsification_method"], f"{identifier}.falsification_method")

    question_ids: set[str] = set()
    open_question_ids: set[str] = set()
    open_question_keys = {
        "id",
        "question",
        "claim_ids",
        "owner",
        "affected_ids",
        "blocks",
        "state",
        "resolution",
        "reason",
    }
    question_values = as_list(payload["open_questions"], "open_questions")
    for index, raw in enumerate(question_values):
        item = as_dict(raw, f"open_questions[{index}]")
        exact_keys(item, open_question_keys, f"open_questions[{index}]")
        identifier = register_id(item, "open question", seen)
        question_ids.add(identifier)
        nonempty(item["question"], f"{identifier}.question")
        refs = ensure_refs(item["claim_ids"], claim_ids, f"{identifier}.claim_ids")
        nonempty(item["owner"], f"{identifier}.owner")
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
            if "open_question" not in {claim_classes[ref] for ref in refs}:
                fail(f"{identifier}にopen_question claimがありません")
            open_question_ids.add(identifier)

    question_review = as_dict(payload["question_review"], "question_review")
    exact_keys(
        question_review,
        {"question_ids", "confirmed_by", "confirmation", "dialogue_complete"},
        "question_review",
    )
    reviewed = string_list(question_review["question_ids"], "question_review.question_ids", non_empty=False)
    if set(reviewed) != question_ids or len(reviewed) != len(question_ids):
        fail("question_review.question_idsが質問一覧全体と一致しません")
    nonempty(question_review["confirmed_by"], "question_review.confirmed_by")
    nonempty(question_review["confirmation"], "question_review.confirmation")
    if question_review["dialogue_complete"] is not True:
        fail("question_review.dialogue_completeは明示確認後のtrueでなければなりません")

    if schema_version == 2:
        catalog = as_dict(payload["interaction_catalog"], "interaction_catalog")
        exact_keys(
            catalog,
            {
                "commands",
                "queries",
                "command_events",
                "query_events",
                "time_events",
                "system_events",
            },
            "interaction_catalog",
        )

        command_event_ids: set[str] = set()
        command_event_keys = {
            "id",
            "name",
            "claim_ids",
            "completed_fact",
            "state_target",
            "state_change",
        }
        for index, raw in enumerate(as_list(catalog["command_events"], "interaction_catalog.command_events")):
            item = as_dict(raw, f"interaction_catalog.command_events[{index}]")
            exact_keys(item, command_event_keys, f"interaction_catalog.command_events[{index}]")
            identifier = register_id(item, "command event", seen)
            command_event_ids.add(identifier)
            for key in ("name", "completed_fact", "state_target"):
                value = nonempty(item[key], f"{identifier}.{key}")
            refs = ensure_refs(item["claim_ids"], claim_ids, f"{identifier}.claim_ids")
            if not {claim_classes[ref] for ref in refs} <= CONFIRMED_CLASSES:
                fail(f"{identifier}が未確認の事実をコマンドイベントへ昇格しています")
            change = as_dict(item["state_change"], f"{identifier}.state_change")
            exact_keys(change, {"from", "to"}, f"{identifier}.state_change")
            nonempty(change["from"], f"{identifier}.state_change.from")
            nonempty(change["to"], f"{identifier}.state_change.to")
            if change["from"] == change["to"]:
                fail(f"{identifier}.state_changeで変更前後が同じです")

        query_event_ids: set[str] = set()
        query_event_keys = {"id", "name", "claim_ids", "completed_fact", "observed_result"}
        for index, raw in enumerate(as_list(catalog["query_events"], "interaction_catalog.query_events")):
            item = as_dict(raw, f"interaction_catalog.query_events[{index}]")
            exact_keys(item, query_event_keys, f"interaction_catalog.query_events[{index}]")
            identifier = register_id(item, "query event", seen)
            query_event_ids.add(identifier)
            for key in ("name", "completed_fact", "observed_result"):
                value = nonempty(item[key], f"{identifier}.{key}")
            refs = ensure_refs(item["claim_ids"], claim_ids, f"{identifier}.claim_ids")
            if not {claim_classes[ref] for ref in refs} <= CONFIRMED_CLASSES:
                fail(f"{identifier}が未確認の事実をクエリイベントへ昇格しています")

        time_event_ids: set[str] = set()
        time_event_keys = {"id", "name", "claim_ids", "occurred_fact", "time_basis"}
        for index, raw in enumerate(as_list(catalog["time_events"], "interaction_catalog.time_events")):
            item = as_dict(raw, f"interaction_catalog.time_events[{index}]")
            exact_keys(item, time_event_keys, f"interaction_catalog.time_events[{index}]")
            identifier = register_id(item, "time event", seen)
            time_event_ids.add(identifier)
            for key in ("name", "occurred_fact", "time_basis"):
                value = nonempty(item[key], f"{identifier}.{key}")
            refs = ensure_refs(item["claim_ids"], claim_ids, f"{identifier}.claim_ids")
            if not {claim_classes[ref] for ref in refs} <= CONFIRMED_CLASSES:
                fail(f"{identifier}が未確認の事実を時間イベントへ昇格しています")

        system_event_keys = {
            "id",
            "name",
            "claim_ids",
            "observed_fact",
            "related_event_ids",
        }
        for index, raw in enumerate(as_list(catalog["system_events"], "interaction_catalog.system_events")):
            item = as_dict(raw, f"interaction_catalog.system_events[{index}]")
            exact_keys(item, system_event_keys, f"interaction_catalog.system_events[{index}]")
            identifier = register_id(item, "system event", seen)
            for key in ("name", "observed_fact"):
                value = nonempty(item[key], f"{identifier}.{key}")
            refs = ensure_refs(item["claim_ids"], claim_ids, f"{identifier}.claim_ids")
            if not {claim_classes[ref] for ref in refs} <= CONFIRMED_CLASSES:
                fail(f"{identifier}が未確認の事実をシステムイベントへ昇格しています")
            ensure_refs(
                item["related_event_ids"],
                command_event_ids | query_event_ids | time_event_ids,
                f"{identifier}.related_event_ids",
                non_empty=False,
            )

        command_ids: set[str] = set()
        command_values = as_list(catalog["commands"], "interaction_catalog.commands")
        command_keys = {
            "id",
            "name",
            "actor_ids",
            "claim_ids",
            "state_target",
            "success_event_ids",
            "counterpart_command_id",
            "counterpart_review",
            "counterpart_rationale",
            "counterpart_open_question_ids",
            "non_success_outcomes",
        }
        outcome_keys = {"no_change", "rejected", "failed"}
        outcome_value_keys = {"status", "statement", "open_question_ids"}
        for index, raw in enumerate(command_values):
            item = as_dict(raw, f"interaction_catalog.commands[{index}]")
            exact_keys(item, command_keys, f"interaction_catalog.commands[{index}]")
            identifier = register_id(item, "command", seen)
            command_ids.add(identifier)
            nonempty(item["name"], f"{identifier}.name")
            nonempty(item["state_target"], f"{identifier}.state_target")
            ensure_refs(item["actor_ids"], stakeholder_ids, f"{identifier}.actor_ids")
            refs = ensure_refs(item["claim_ids"], claim_ids, f"{identifier}.claim_ids")
            if not {claim_classes[ref] for ref in refs} <= CONFIRMED_CLASSES:
                fail(f"{identifier}が未確認の操作をコマンドへ昇格しています")
            ensure_refs(
                item["success_event_ids"],
                command_event_ids,
                f"{identifier}.success_event_ids",
            )
            counterpart = item["counterpart_command_id"]
            if counterpart is not None and not isinstance(counterpart, str):
                fail(f"{identifier}.counterpart_command_idはnullまたは文字列でなければなりません")
            review = item["counterpart_review"]
            if review not in {"paired", "not_applicable", "unresolved"}:
                fail(f"{identifier}.counterpart_reviewが不正です")
            if (review == "paired") != (counterpart is not None):
                fail(f"{identifier}.counterpart_reviewとcounterpart_command_idが一致しません")
            nonempty(item["counterpart_rationale"], f"{identifier}.counterpart_rationale")
            counterpart_questions = ensure_refs(
                item["counterpart_open_question_ids"],
                open_question_ids,
                f"{identifier}.counterpart_open_question_ids",
                non_empty=review == "unresolved",
            )
            if review != "unresolved" and counterpart_questions:
                fail(f"{identifier}の解決済み対操作レビューが未決を参照しています")
            outcomes = as_dict(item["non_success_outcomes"], f"{identifier}.non_success_outcomes")
            exact_keys(outcomes, outcome_keys, f"{identifier}.non_success_outcomes")
            for outcome_name in sorted(outcome_keys):
                outcome = as_dict(outcomes[outcome_name], f"{identifier}.{outcome_name}")
                exact_keys(outcome, outcome_value_keys, f"{identifier}.{outcome_name}")
                status = outcome["status"]
                if status not in {"defined", "unresolved", "not_applicable"}:
                    fail(f"{identifier}.{outcome_name}.statusが不正です")
                statement = outcome["statement"]
                refs = ensure_refs(
                    outcome["open_question_ids"],
                    open_question_ids,
                    f"{identifier}.{outcome_name}.open_question_ids",
                    non_empty=status == "unresolved",
                )
                if status == "defined":
                    nonempty(statement, f"{identifier}.{outcome_name}.statement")
                    if refs:
                        fail(f"{identifier}.{outcome_name}の定義済み結果が未決を参照しています")
                elif statement is not None:
                    fail(f"{identifier}.{outcome_name}.statementは未決または非該当ではnullにします")
                if status == "not_applicable" and refs:
                    fail(f"{identifier}.{outcome_name}の非該当結果が未決を参照しています")

        commands_by_id = {item["id"]: item for item in command_values}
        for item in command_values:
            counterpart = item["counterpart_command_id"]
            if counterpart is None:
                continue
            if counterpart not in command_ids:
                fail(f"{item['id']}.counterpart_command_idが未解決です")
            if commands_by_id[counterpart]["counterpart_command_id"] != item["id"]:
                fail(f"{item['id']}と{counterpart}が対になる操作として相互参照されていません")

        query_keys = {
            "id",
            "name",
            "actor_ids",
            "claim_ids",
            "reads",
            "success_event_ids",
        }
        for index, raw in enumerate(as_list(catalog["queries"], "interaction_catalog.queries")):
            item = as_dict(raw, f"interaction_catalog.queries[{index}]")
            exact_keys(item, query_keys, f"interaction_catalog.queries[{index}]")
            identifier = register_id(item, "query", seen)
            nonempty(item["name"], f"{identifier}.name")
            nonempty(item["reads"], f"{identifier}.reads")
            ensure_refs(item["actor_ids"], stakeholder_ids, f"{identifier}.actor_ids")
            refs = ensure_refs(item["claim_ids"], claim_ids, f"{identifier}.claim_ids")
            if not {claim_classes[ref] for ref in refs} <= CONFIRMED_CLASSES:
                fail(f"{identifier}が未確認の操作をクエリへ昇格しています")
            ensure_refs(
                item["success_event_ids"],
                query_event_ids,
                f"{identifier}.success_event_ids",
            )

    known_before_affected = (
        set(seen)
        | in_scope
        | out_scope
        | system_ids
        | external_ids
    )
    for item in hypothesis_values:
        ensure_refs(
            item["affected_ids"],
            known_before_affected,
            f"{item['id']}.affected_ids",
        )
    for item in question_values:
        ensure_refs(
            item["affected_ids"],
            known_before_affected,
            f"{item['id']}.affected_ids",
        )

    solution_keys = {
        "id",
        "statement",
        "classification",
        "claim_ids",
        "rationale",
        "linked_id",
        "routed_to",
    }
    for index, raw in enumerate(as_list(payload["solution_inputs"], "solution_inputs")):
        item = as_dict(raw, f"solution_inputs[{index}]")
        exact_keys(item, solution_keys, f"solution_inputs[{index}]")
        identifier = register_id(item, "solution input", seen)
        nonempty(item["statement"], f"{identifier}.statement")
        refs = ensure_refs(item["claim_ids"], claim_ids, f"{identifier}.claim_ids")
        nonempty(item["rationale"], f"{identifier}.rationale")
        classification = item["classification"]
        linked = item["linked_id"]
        routed = nonempty(item["routed_to"], f"{identifier}.routed_to")
        if classification == "constraint":
            if linked not in constraint_ids:
                fail(f"{identifier}.linked_idがconstraintを参照していません")
            if not {claim_classes[ref] for ref in refs} <= CONFIRMED_CLASSES:
                fail(f"{identifier}が未確認のHowをconstraintへ昇格しています")
        elif classification == "hypothesis":
            if linked not in hypothesis_ids:
                fail(f"{identifier}.linked_idがhypothesisを参照していません")
            if "hypothesis" not in {claim_classes[ref] for ref in refs}:
                fail(f"{identifier}のHow hypothesis根拠がありません")
        elif classification == "design_proposal":
            if linked is not None or routed != "design-cloud-architecture":
                fail(f"{identifier}のdesign proposalが要求へ逆流しています")
            if "hypothesis" not in {claim_classes[ref] for ref in refs}:
                fail(f"{identifier}のdesign proposal根拠がhypothesisではありません")
        else:
            fail(f"{identifier}.classificationが不正です")

    if schema_version == 2:
        validate_terminology(payload["terminology"], set(seen))

    if not requirement_ids and not derived_requirement_ids and not hypothesis_ids and not open_question_ids:
        fail("requirements、derived_requirements、hypotheses、open_questionsのいずれかが必要です")

    handoff = as_dict(payload["handoff"], "handoff")
    exact_keys(handoff, {"ready", "blocking_question_ids", "downstream"}, "handoff")
    ready = bool_value(handoff["ready"], "handoff.ready")
    blocking = ensure_refs(
        handoff["blocking_question_ids"],
        open_question_ids,
        "handoff.blocking_question_ids",
        non_empty=not ready,
    )
    if ready and blocking:
        fail("handoff.ready=trueでblocking questionを持てません")
    expected_state = "ready_for_downstream" if ready else "saved_with_open_questions"
    if artifact["state"] != expected_state:
        fail("artifact.stateとhandoff.readyが一致しません")
    downstream = as_dict(handoff["downstream"], "handoff.downstream")
    exact_keys(downstream, DOWNSTREAM_KEYS, "handoff.downstream")
    downstream_allowed = (
        requirement_ids
        | derived_requirement_ids
        | design_decision_ids
        | constraint_ids
        | hypothesis_ids
        | open_question_ids
    )
    for key in sorted(DOWNSTREAM_KEYS):
        ensure_refs(
            downstream[key],
            downstream_allowed,
            f"handoff.downstream.{key}",
            non_empty=False,
        )


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
    target = repo / "system-design" / "requirements" / f"{slug}.requirements.json"
    current_path = repo
    for part in target.relative_to(repo).parts:
        current_path = current_path / part
        if current_path.exists() and current_path.is_symlink():
            fail(f"保存先のpathにsymlinkがあります: {current_path}")
    if target.exists():
        if expected_version is None:
            fail("既存正本を更新するには--expected-versionが必要です")
        current = check_file(target)
        current_version = current["artifact"]["version"]
        if current_version != expected_version:
            fail(
                "既存正本versionが期待値と一致しません: "
                f"expected={expected_version}, actual={current_version}"
            )
        if payload["artifact"]["id"] != current["artifact"]["id"]:
            fail("更新でartifact.idを変更できません")
        if payload["artifact"]["version"] != current_version + 1:
            fail("更新後artifact.versionは現在version+1でなければなりません")
    elif expected_version is not None:
        fail("初回保存に--expected-versionを指定できません")

    target.parent.mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=False,
    ) + "\n"
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
        repo = safe_repo(args.repo)
        result = write_artifact(
            repo,
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
