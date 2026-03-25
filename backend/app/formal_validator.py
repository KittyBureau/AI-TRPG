from __future__ import annotations

from collections import deque

from backend.domain.formal_gameplay_model import (
    Edge,
    FormalGameplayModel,
    ValidationIssue,
    ValidationResult,
)


def validate_formal_model(model: FormalGameplayModel) -> ValidationResult:
    issues: list[ValidationIssue] = []
    node_index = {node.id: node for node in model.nodes}

    issues.extend(_validate_missing_structure(model, node_index))

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
        _validate_gate_dependencies(model, node_index, ungated_graph, start_area_valid)
    )
    issues.extend(
        _validate_item_reachability(model, node_index, ungated_graph, start_area_valid)
    )

    main_path_solvable = goal_reachable and not any(
        issue.severity == "error" for issue in issues
    )
    return ValidationResult(main_path_solvable=main_path_solvable, issues=issues)


def _validate_missing_structure(
    model: FormalGameplayModel,
    node_index: dict[str, object],
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
    ungated_graph: dict[str, set[str]],
    start_area_valid: bool,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not start_area_valid:
        return issues

    for gate_id in sorted(
        node.id for node in model.nodes if node.type == "gate" and node.id in node_index
    ):
        required_item_ids = [
            edge.to_id
            for edge in model.edges
            if edge.type == "requires" and edge.from_id == gate_id
        ]
        gate_area_id = _located_area_id(model.edges, gate_id)
        if not required_item_ids or gate_area_id is None:
            issues.append(
                ValidationIssue(
                    code="critical_gate_unsatisfied",
                    refs={
                        "gate_id": gate_id,
                        "required_item_ids": required_item_ids,
                        "gate_area_id": gate_area_id,
                    },
                )
            )
            continue

        satisfiable = False
        for item_id in required_item_ids:
            clue_source_ids = [
                edge.from_id
                for edge in model.edges
                if edge.type == "reveals" and edge.to_id == item_id
            ]
            for clue_source_id in clue_source_ids:
                clue_area_id = _located_area_id(model.edges, clue_source_id)
                if clue_area_id is None:
                    continue
                if _is_reachable(ungated_graph, model.start_area_id, clue_area_id) and _is_reachable(
                    ungated_graph, model.start_area_id, gate_area_id
                ):
                    satisfiable = True
                    break
            if satisfiable:
                break

        if not satisfiable:
            issues.append(
                ValidationIssue(
                    code="critical_gate_unsatisfied",
                    refs={
                        "gate_id": gate_id,
                        "required_item_ids": required_item_ids,
                        "gate_area_id": gate_area_id,
                    },
                )
            )
    return issues


def _validate_item_reachability(
    model: FormalGameplayModel,
    node_index: dict[str, object],
    ungated_graph: dict[str, set[str]],
    start_area_valid: bool,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not start_area_valid:
        return issues

    for item_id in sorted(
        node.id
        for node in model.nodes
        if node.type == "item_dependency" and node.id in node_index
    ):
        clue_source_ids = [
            edge.from_id
            for edge in model.edges
            if edge.type == "reveals" and edge.to_id == item_id
        ]
        if not clue_source_ids:
            issues.append(
                ValidationIssue(
                    code="critical_item_unreachable",
                    refs={"item_id": item_id, "reason": "missing_clue_source"},
                )
            )
            continue

        reachable = False
        for clue_source_id in clue_source_ids:
            clue_area_id = _located_area_id(model.edges, clue_source_id)
            if clue_area_id is None:
                continue
            if _is_reachable(ungated_graph, model.start_area_id, clue_area_id):
                reachable = True
                break

        if not reachable:
            issues.append(
                ValidationIssue(
                    code="critical_item_unreachable",
                    refs={"item_id": item_id, "clue_source_ids": clue_source_ids},
                )
            )
    return issues


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
