from __future__ import annotations

from collections import deque

from backend.domain.formal_gameplay_model import (
    DependencyGroup,
    Edge,
    FormalGameplayModel,
    GateClue,
    GateClueSupportGap,
    GateAuthoringAudit,
    GateQualitySummary,
    OverallAuthoringAuditSummary,
    Node,
    ValidationIssue,
    ValidationResult,
)


def validate_formal_model(model: FormalGameplayModel) -> ValidationResult:
    issues: list[ValidationIssue] = []
    node_index = {node.id: node for node in model.nodes}
    dependency_group_index = {
        dependency_group.id: dependency_group
        for dependency_group in model.dependency_groups
    }
    gate_clues = list(model.gate_clues)
    gate_clue_support_gaps = list(model.gate_clue_support_gaps)

    issues.extend(
        _validate_missing_structure(
            model,
            node_index,
            dependency_group_index,
            gate_clues,
            gate_clue_support_gaps,
        )
    )

    start_area_valid = (
        model.start_area_id in node_index
        and node_index[model.start_area_id].type == "area"
    )
    graph = _build_area_graph(model.edges)
    ungated_graph = _build_ungated_area_graph(model, node_index)

    goal_reachable = False
    if start_area_valid and not _has_missing_goal_targets(model, node_index):
        goal_reachable = _is_any_goal_reachable(model, node_index, graph)
        if not goal_reachable:
            issues.append(
                ValidationIssue(
                    code="goal_unreachable",
                    refs={
                        "start_area_id": model.start_area_id,
                        "goal_ids": [goal.id for goal in model.goals],
                    },
                )
            )

    issues.extend(
        _validate_gate_dependencies(
            model,
            node_index,
            dependency_group_index,
            ungated_graph,
            start_area_valid,
        )
    )
    issues.extend(
        _validate_item_reachability(
            model,
            node_index,
            dependency_group_index,
            ungated_graph,
            start_area_valid,
        )
    )
    issues.extend(
        _validate_any_of_path_coverage(
            model,
            node_index,
            dependency_group_index,
            ungated_graph,
            start_area_valid,
        )
    )
    issues.extend(
        _validate_any_of_clue_support(
            model,
            node_index,
            dependency_group_index,
            gate_clues,
            gate_clue_support_gaps,
            start_area_valid,
        )
    )

    main_path_solvable = goal_reachable and not any(
        issue.severity == "error" for issue in issues
    )
    gate_quality_statuses = _build_gate_quality_statuses(model, node_index, issues)
    overall_quality_status = _derive_overall_quality_status(gate_quality_statuses)
    gate_authoring_audits = _build_gate_authoring_audits(
        model,
        node_index,
        gate_quality_statuses,
        gate_clue_support_gaps,
        issues,
    )
    overall_authoring_audit = _build_overall_authoring_audit(
        overall_quality_status,
        gate_quality_statuses,
        gate_authoring_audits,
        gate_clue_support_gaps,
        issues,
    )
    return ValidationResult(
        main_path_solvable=main_path_solvable,
        gate_quality_statuses=gate_quality_statuses,
        overall_quality_status=overall_quality_status,
        gate_authoring_audits=gate_authoring_audits,
        overall_authoring_audit=overall_authoring_audit,
        issues=issues,
    )


def _validate_missing_structure(
    model: FormalGameplayModel,
    node_index: dict[str, object],
    dependency_group_index: dict[str, DependencyGroup],
    gate_clues: list[GateClue],
    gate_clue_support_gaps: list[GateClueSupportGap],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if model.start_area_id not in node_index:
        issues.append(
            ValidationIssue(
                code="missing_structure",
                refs={"kind": "start_area", "missing_id": model.start_area_id},
            )
        )

    for goal in model.goals:
        if goal.target_id not in node_index:
            issues.append(
                ValidationIssue(
                    code="missing_structure",
                    refs={
                        "kind": "goal_target",
                        "goal_id": goal.id,
                        "missing_id": goal.target_id,
                    },
                )
            )

    for edge in model.edges:
        missing_ids = [
            node_id
            for node_id in (edge.from_id, edge.to_id)
            if node_id not in node_index
        ]
        if not missing_ids:
            continue
        issues.append(
            ValidationIssue(
                code="missing_structure",
                refs={
                    "kind": "edge_ref",
                    "edge_type": edge.type,
                    "missing_ids": missing_ids,
                    "from_id": edge.from_id,
                    "to_id": edge.to_id,
                },
            )
        )

    for node in model.nodes:
        if node.type != "gate" or not node.dependency_group_id:
            continue
        if node.dependency_group_id not in dependency_group_index:
            issues.append(
                ValidationIssue(
                    code="missing_structure",
                    refs={
                        "kind": "dependency_group",
                        "gate_id": node.id,
                        "missing_id": node.dependency_group_id,
                    },
                )
            )

    for dependency_group in model.dependency_groups:
        missing_ids = [
            node_id for node_id in dependency_group.node_ids if node_id not in node_index
        ]
        if not missing_ids:
            continue
        issues.append(
            ValidationIssue(
                code="missing_structure",
                refs={
                    "kind": "dependency_group_ref",
                    "dependency_group_id": dependency_group.id,
                    "missing_ids": missing_ids,
                },
            )
        )

    for gate_clue in gate_clues:
        missing_ids = [
            node_id
            for node_id in [gate_clue.gate_id, *gate_clue.supported_items]
            if node_id not in node_index
        ]
        if not missing_ids:
            continue
        issues.append(
            ValidationIssue(
                code="missing_structure",
                refs={
                    "kind": "gate_clue_ref",
                    "clue_id": gate_clue.clue_id,
                    "missing_ids": missing_ids,
                },
            )
        )

    for support_gap in gate_clue_support_gaps:
        missing_ids = [
            node_id
            for node_id in [support_gap.gate_id, support_gap.item_id]
            if node_id not in node_index
        ]
        if not missing_ids:
            continue
        issues.append(
            ValidationIssue(
                code="missing_structure",
                refs={
                    "kind": "gate_clue_support_gap_ref",
                    "gate_id": support_gap.gate_id,
                    "item_id": support_gap.item_id,
                    "missing_ids": missing_ids,
                },
            )
        )
    return issues


def _has_missing_goal_targets(
    model: FormalGameplayModel,
    node_index: dict[str, object],
) -> bool:
    return any(goal.target_id not in node_index for goal in model.goals)


def _is_any_goal_reachable(
    model: FormalGameplayModel,
    node_index: dict[str, object],
    graph: dict[str, set[str]],
) -> bool:
    if model.start_area_id not in graph and model.start_area_id not in node_index:
        return False
    for goal in model.goals:
        target = node_index.get(goal.target_id)
        if target is None:
            continue
        if goal.type == "enter_area" and getattr(target, "type", None) == "area":
            if _is_reachable(graph, model.start_area_id, goal.target_id):
                return True
            continue
        if goal.type == "interact_entity":
            target_area_id = _located_area_id(model.edges, goal.target_id)
            if isinstance(target_area_id, str) and _is_reachable(
                graph, model.start_area_id, target_area_id
            ):
                return True
    return False


def _validate_gate_dependencies(
    model: FormalGameplayModel,
    node_index: dict[str, object],
    dependency_group_index: dict[str, DependencyGroup],
    ungated_graph: dict[str, set[str]],
    start_area_valid: bool,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not start_area_valid:
        return issues

    for gate in _iter_gate_nodes(model, node_index):
        dependency_mode, required_item_ids = _resolve_gate_dependency_items(
            gate, model, dependency_group_index
        )
        gate_area_id = _located_area_id(model.edges, gate.id)
        if not required_item_ids or gate_area_id is None:
            issues.append(
                ValidationIssue(
                    code="critical_gate_unsatisfied",
                    refs={
                        "gate_id": gate.id,
                        "dependency_mode": dependency_mode,
                        "required_item_ids": required_item_ids,
                        "gate_area_id": gate_area_id,
                    },
                )
            )
            continue

        gate_area_reachable = _is_reachable(
            ungated_graph, model.start_area_id, gate_area_id
        )
        satisfiable_items = [
            item_id
            for item_id in required_item_ids
            if _item_dependency_reachable(
                model, ungated_graph, model.start_area_id, item_id
            )
        ]

        if dependency_mode == "any_of":
            satisfiable = gate_area_reachable and bool(satisfiable_items)
        else:
            satisfiable = gate_area_reachable and len(satisfiable_items) == len(
                required_item_ids
            )

        if not satisfiable:
            issues.append(
                ValidationIssue(
                    code="critical_gate_unsatisfied",
                    refs={
                        "gate_id": gate.id,
                        "dependency_mode": dependency_mode,
                        "required_item_ids": required_item_ids,
                        "gate_area_id": gate_area_id,
                    },
                )
            )
    return issues


def _validate_item_reachability(
    model: FormalGameplayModel,
    node_index: dict[str, object],
    dependency_group_index: dict[str, DependencyGroup],
    ungated_graph: dict[str, set[str]],
    start_area_valid: bool,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not start_area_valid:
        return issues

    for gate in _iter_gate_nodes(model, node_index):
        dependency_mode, required_item_ids = _resolve_gate_dependency_items(
            gate, model, dependency_group_index
        )
        if not required_item_ids:
            continue

        if dependency_mode == "any_of":
            if any(
                _item_dependency_reachable(
                    model, ungated_graph, model.start_area_id, item_id
                )
                for item_id in required_item_ids
            ):
                continue
            issues.append(
                ValidationIssue(
                    code="critical_item_unreachable",
                    refs={
                        "gate_id": gate.id,
                        "mode": "any_of",
                        "item_ids": required_item_ids,
                    },
                )
            )
            continue

        for item_id in required_item_ids:
            clue_source_ids = _clue_source_ids_for_item(model.edges, item_id)
            if not clue_source_ids:
                issues.append(
                    ValidationIssue(
                        code="critical_item_unreachable",
                        refs={"item_id": item_id, "reason": "missing_clue_source"},
                    )
                )
                continue
            if _item_dependency_reachable(
                model, ungated_graph, model.start_area_id, item_id
            ):
                continue
            issues.append(
                ValidationIssue(
                    code="critical_item_unreachable",
                    refs={"item_id": item_id, "clue_source_ids": clue_source_ids},
                )
            )
    return issues


def _validate_any_of_path_coverage(
    model: FormalGameplayModel,
    node_index: dict[str, object],
    dependency_group_index: dict[str, DependencyGroup],
    ungated_graph: dict[str, set[str]],
    start_area_valid: bool,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not start_area_valid:
        return issues

    for gate in _iter_gate_nodes(model, node_index):
        dependency_mode, required_item_ids = _resolve_gate_dependency_items(
            gate, model, dependency_group_index
        )
        if dependency_mode != "any_of":
            continue

        reachable_signatures: dict[str, tuple[str, ...]] = {}
        for item_id in required_item_ids:
            signature = _reachable_support_area_signature(
                model, ungated_graph, model.start_area_id, item_id
            )
            if signature:
                reachable_signatures[item_id] = signature

        if len(reachable_signatures) == 0:
            continue

        distinct_signatures = sorted({signature for signature in reachable_signatures.values()})
        if len(distinct_signatures) >= 2:
            continue

        issues.append(
            ValidationIssue(
                code="multi_path_coverage_missing",
                severity="warning",
                refs={
                    "gate_id": gate.id,
                    "dependency_group_id": gate.dependency_group_id,
                    "reachable_item_ids": sorted(reachable_signatures.keys()),
                    "reachable_support_area_signatures": [
                        list(signature) for signature in distinct_signatures
                    ],
                },
            )
        )
    return issues


def _validate_any_of_clue_support(
    model: FormalGameplayModel,
    node_index: dict[str, object],
    dependency_group_index: dict[str, DependencyGroup],
    gate_clues: list[GateClue],
    gate_clue_support_gaps: list[GateClueSupportGap],
    start_area_valid: bool,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not start_area_valid:
        return issues

    for gate in _iter_gate_nodes(model, node_index):
        dependency_mode, required_item_ids = _resolve_gate_dependency_items(
            gate, model, dependency_group_index
        )
        if dependency_mode != "any_of":
            continue

        for item_id in required_item_ids:
            supporting_clue_ids = _supporting_clue_ids_for_candidate(
                gate_clues, gate.id, item_id
            )
            if supporting_clue_ids:
                continue
            support_gap = _support_gap_for_candidate(
                gate_clue_support_gaps,
                gate.id,
                item_id,
            )
            refs = {
                "gate_id": gate.id,
                "dependency_group_id": gate.dependency_group_id,
                "item_id": item_id,
            }
            if support_gap is not None:
                refs["support_gap_reason"] = support_gap.reason
                refs["support_gap_source"] = support_gap.source
            issues.append(
                ValidationIssue(
                    code="missing_clue_support_for_candidate",
                    severity="warning",
                    refs=refs,
                )
            )
    return issues


def _iter_gate_nodes(
    model: FormalGameplayModel,
    node_index: dict[str, object],
) -> list[Node]:
    return sorted(
        [
            node
            for node in model.nodes
            if node.type == "gate" and node.id in node_index
        ],
        key=lambda node: node.id,
    )


def _resolve_gate_dependency_items(
    gate: Node,
    model: FormalGameplayModel,
    dependency_group_index: dict[str, DependencyGroup],
) -> tuple[str, list[str]]:
    if gate.dependency_group_id:
        dependency_group = dependency_group_index.get(gate.dependency_group_id)
        if dependency_group is None:
            return "all_of", []
        return dependency_group.mode, list(dict.fromkeys(dependency_group.node_ids))

    required_item_ids = [
        edge.to_id
        for edge in model.edges
        if edge.type == "requires" and edge.from_id == gate.id
    ]
    return "all_of", list(dict.fromkeys(required_item_ids))


def _clue_source_ids_for_item(edges: list[Edge], item_id: str) -> list[str]:
    return [
        edge.from_id for edge in edges if edge.type == "reveals" and edge.to_id == item_id
    ]


def _item_dependency_reachable(
    model: FormalGameplayModel,
    ungated_graph: dict[str, set[str]],
    start_area_id: str,
    item_id: str,
) -> bool:
    for clue_source_id in _clue_source_ids_for_item(model.edges, item_id):
        clue_area_id = _located_area_id(model.edges, clue_source_id)
        if clue_area_id is None:
            continue
        if _is_reachable(ungated_graph, start_area_id, clue_area_id):
            return True
    return False


def _reachable_support_area_signature(
    model: FormalGameplayModel,
    ungated_graph: dict[str, set[str]],
    start_area_id: str,
    item_id: str,
) -> tuple[str, ...]:
    area_ids: set[str] = set()
    for clue_source_id in _clue_source_ids_for_item(model.edges, item_id):
        clue_area_id = _located_area_id(model.edges, clue_source_id)
        if clue_area_id is None:
            continue
        if _is_reachable(ungated_graph, start_area_id, clue_area_id):
            area_ids.add(clue_area_id)
    return tuple(sorted(area_ids))


def _supporting_clue_ids_for_candidate(
    gate_clues: list[GateClue],
    gate_id: str,
    item_id: str,
) -> list[str]:
    return sorted(
        gate_clue.clue_id
        for gate_clue in gate_clues
        if gate_clue.gate_id == gate_id and item_id in gate_clue.supported_items
    )


def _support_gap_for_candidate(
    gate_clue_support_gaps: list[GateClueSupportGap],
    gate_id: str,
    item_id: str,
) -> GateClueSupportGap | None:
    for support_gap in gate_clue_support_gaps:
        if support_gap.gate_id == gate_id and support_gap.item_id == item_id:
            return support_gap
    return None


def _build_gate_quality_statuses(
    model: FormalGameplayModel,
    node_index: dict[str, object],
    issues: list[ValidationIssue],
) -> list[GateQualitySummary]:
    gate_ids = [gate.id for gate in _iter_gate_nodes(model, node_index)]
    gate_issue_codes: dict[str, set[str]] = {gate_id: set() for gate_id in gate_ids}
    for issue in issues:
        gate_id = issue.refs.get("gate_id")
        if gate_id in gate_issue_codes:
            gate_issue_codes[gate_id].add(issue.code)

    summaries: list[GateQualitySummary] = []
    for gate_id in gate_ids:
        issue_codes = gate_issue_codes[gate_id]
        if "critical_gate_unsatisfied" in issue_codes:
            quality_status = "failing"
        elif issue_codes & {
            "multi_path_coverage_missing",
            "missing_clue_support_for_candidate",
        }:
            quality_status = "weak"
        else:
            quality_status = "good"
        summaries.append(
            GateQualitySummary(gate_id=gate_id, quality_status=quality_status)
        )
    return summaries


def _derive_overall_quality_status(
    gate_quality_statuses: list[GateQualitySummary],
) -> str:
    statuses = {summary.quality_status for summary in gate_quality_statuses}
    if "failing" in statuses:
        return "failing"
    if "weak" in statuses:
        return "weak"
    return "good"


def _build_gate_authoring_audits(
    model: FormalGameplayModel,
    node_index: dict[str, object],
    gate_quality_statuses: list[GateQualitySummary],
    gate_clue_support_gaps: list[GateClueSupportGap],
    issues: list[ValidationIssue],
) -> list[GateAuthoringAudit]:
    quality_by_gate = {
        summary.gate_id: summary.quality_status for summary in gate_quality_statuses
    }
    shaping_gaps_by_gate: dict[str, bool] = {
        gate.id: False for gate in _iter_gate_nodes(model, node_index)
    }
    for support_gap in gate_clue_support_gaps:
        if support_gap.gate_id in shaping_gaps_by_gate:
            shaping_gaps_by_gate[support_gap.gate_id] = True

    issue_codes_by_gate: dict[str, list[str]] = {
        gate.id: [] for gate in _iter_gate_nodes(model, node_index)
    }
    categories_by_gate: dict[str, set[str]] = {
        gate.id: set() for gate in _iter_gate_nodes(model, node_index)
    }
    for issue in issues:
        gate_id = issue.refs.get("gate_id")
        if gate_id not in issue_codes_by_gate:
            continue
        issue_codes_by_gate[gate_id].append(issue.code)
        category = _issue_category_for_code(issue.code)
        if category is not None:
            categories_by_gate[gate_id].add(category)

    audits: list[GateAuthoringAudit] = []
    for gate in _iter_gate_nodes(model, node_index):
        gate_id = gate.id
        if shaping_gaps_by_gate.get(gate_id):
            categories_by_gate[gate_id].add("shaping_gap_related")
        audits.append(
            GateAuthoringAudit(
                gate_id=gate_id,
                quality_status=quality_by_gate.get(gate_id, "good"),
                issue_categories=sorted(categories_by_gate[gate_id]),
                issues=sorted(set(issue_codes_by_gate[gate_id])),
                has_shaping_gap=shaping_gaps_by_gate.get(gate_id, False),
            )
        )
    return audits


def _build_overall_authoring_audit(
    overall_quality_status: str,
    gate_quality_statuses: list[GateQualitySummary],
    gate_authoring_audits: list[GateAuthoringAudit],
    gate_clue_support_gaps: list[GateClueSupportGap],
    issues: list[ValidationIssue],
) -> OverallAuthoringAuditSummary:
    gate_count_by_quality = {"good": 0, "weak": 0, "failing": 0}
    for summary in gate_quality_statuses:
        gate_count_by_quality[summary.quality_status] = (
            gate_count_by_quality.get(summary.quality_status, 0) + 1
        )

    issue_count_by_category = {
        "solvability_related": 0,
        "path_coverage_related": 0,
        "clue_support_related": 0,
        "shaping_gap_related": 0,
    }
    for issue in issues:
        category = _issue_category_for_code(issue.code)
        if category is None:
            continue
        issue_count_by_category[category] += 1
    issue_count_by_category["shaping_gap_related"] = len(gate_clue_support_gaps)

    gates_with_shaping_gaps = sorted(
        {
            audit.gate_id
            for audit in gate_authoring_audits
            if audit.has_shaping_gap
        }
    )
    return OverallAuthoringAuditSummary(
        overall_quality_status=overall_quality_status,
        gate_count_by_quality=gate_count_by_quality,
        issue_count_by_category=issue_count_by_category,
        gates_with_shaping_gaps=gates_with_shaping_gaps,
    )


def _issue_category_for_code(issue_code: str) -> str | None:
    if issue_code == "critical_gate_unsatisfied":
        return "solvability_related"
    if issue_code == "multi_path_coverage_missing":
        return "path_coverage_related"
    if issue_code == "missing_clue_support_for_candidate":
        return "clue_support_related"
    return None


def _build_area_graph(edges: list[Edge]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for edge in edges:
        if edge.type != "transition":
            continue
        graph.setdefault(edge.from_id, set()).add(edge.to_id)
        graph.setdefault(edge.to_id, set())
    return graph


def _build_ungated_area_graph(
    model: FormalGameplayModel,
    node_index: dict[str, object],
) -> dict[str, set[str]]:
    graph = _build_area_graph(model.edges)
    for node in model.nodes:
        if node.type != "gate" or node.id not in node_index:
            continue
        gate_area_id = _located_area_id(model.edges, node.id)
        blocked_area_ids = [
            edge.to_id
            for edge in model.edges
            if edge.type == "blocks_transition" and edge.from_id == node.id
        ]
        if gate_area_id is None:
            continue
        for blocked_area_id in blocked_area_ids:
            graph.setdefault(gate_area_id, set()).discard(blocked_area_id)
            graph.setdefault(blocked_area_id, set()).discard(gate_area_id)
    return graph


def _located_area_id(edges: list[Edge], node_id: str) -> str | None:
    for edge in edges:
        if edge.type == "located_in" and edge.from_id == node_id:
            return edge.to_id
    return None


def _is_reachable(graph: dict[str, set[str]], start: str, target: str) -> bool:
    if start == target:
        return True
    if start not in graph or target not in graph:
        return False
    queue = deque([start])
    visited = {start}
    while queue:
        current = queue.popleft()
        for neighbor in sorted(graph.get(current, set())):
            if neighbor in visited:
                continue
            if neighbor == target:
                return True
            visited.add(neighbor)
            queue.append(neighbor)
    return False
