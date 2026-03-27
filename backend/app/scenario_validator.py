from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from backend.app.scenario_templates import get_scenario_template
from backend.domain.scenario_models import (
    MaterializedScenario,
    ScenarioValidationIssue,
    ScenarioValidationResult,
)


class ScenarioValidationError(ValueError):
    def __init__(self, result: ScenarioValidationResult):
        self.result = result
        messages = [issue.message for issue in result.issues]
        super().__init__("; ".join(messages) if messages else "scenario validation failed")


@dataclass(frozen=True)
class _ScenarioStaticValidationView:
    start_area_id: str
    clue_area_id: str
    clue_source_id: str
    revealed_item_id: str
    gate_area_id: str
    target_area_id: str
    gate_dependency_mode: str
    required_item_ids: tuple[str, ...]
    graph: dict[str, set[str]]
    ungated_graph: dict[str, set[str]]
    item_source_area_ids: dict[str, tuple[str, ...]]


def validate_materialized_scenario(
    scenario: MaterializedScenario,
) -> ScenarioValidationResult:
    template = get_scenario_template(scenario.template_id)

    if scenario.template_version != template.template_version:
        raise ValueError("scenario template_version does not match the template registry")
    if scenario.params.scenario_template != template.template_id:
        raise ValueError("scenario params do not match the materialized template_id")

    issues: list[ScenarioValidationIssue] = []
    issues.extend(_validate_required_roles(scenario))
    issues.extend(_validate_area_count(scenario))
    issues.extend(_validate_entities_and_items(scenario))
    issues.extend(_validate_goal_and_gate_rules(scenario))
    issues.extend(_validate_dependency_groups(scenario))
    issues.extend(_validate_progression_contract(scenario))

    blocking_issue_codes = {
        "missing_required_role",
        "topology_contract_invalid",
        "entity_binding_invalid",
        "goal_rule_invalid",
        "gate_rule_invalid",
        "dependency_group_invalid",
    }
    if not any(issue.code in blocking_issue_codes for issue in issues):
        static_view = _build_static_validation_view(scenario)
        issues.extend(
            _validate_static_gameplay(
                scenario,
                static_view,
            )
        )
        issues.extend(
            _validate_static_clue_support(
                scenario,
                static_view,
            )
        )

    result = ScenarioValidationResult(
        ok=not issues,
        template_id=scenario.template_id,
        checked_area_count=len(scenario.topology.areas),
        issues=tuple(issues),
    )
    if issues:
        raise ScenarioValidationError(result)
    return result


def _issue(code: str, message: str, **refs: object) -> ScenarioValidationIssue:
    return ScenarioValidationIssue(code=code, message=message, refs=refs)


def _validate_required_roles(
    scenario: MaterializedScenario,
) -> list[ScenarioValidationIssue]:
    issues: list[ScenarioValidationIssue] = []
    roles = scenario.roles
    required_values = {
        "start_area_id": roles.start_area_id,
        "hint_source_id": roles.hint_source_id,
        "clue_area_id": roles.clue_area_id,
        "clue_source_id": roles.clue_source_id,
        "revealed_item_id": roles.revealed_item_id,
        "gate_area_id": roles.gate_area_id,
        "gate_entity_id": roles.gate_entity_id,
        "required_item_id": roles.required_item_id,
        "target_area_id": roles.target_area_id,
    }
    for label, value in required_values.items():
        if not isinstance(value, str) or not value.strip():
            issues.append(
                _issue(
                    "missing_required_role",
                    f"missing required role value: {label}",
                    role=label,
                )
            )

    area_ids = set(scenario.topology.areas.keys())
    for role_name, area_id, expected_kind, missing_message, invalid_message in [
        (
            "start_area_id",
            roles.start_area_id,
            "start",
            "start area role is missing from topology",
            "start area role does not point to a start area",
        ),
        (
            "clue_area_id",
            roles.clue_area_id,
            "clue",
            "clue area role is missing from topology",
            "clue area role does not point to a clue area",
        ),
        (
            "gate_area_id",
            roles.gate_area_id,
            "gate",
            "gate area role is missing from topology",
            "gate area role does not point to a gate area",
        ),
        (
            "target_area_id",
            roles.target_area_id,
            "target",
            "target area role is missing from topology",
            "target area role does not point to a target area",
        ),
    ]:
        if area_id not in area_ids:
            issues.append(
                _issue("missing_required_role", missing_message, role=role_name)
            )
            continue
        if scenario.topology.areas[area_id].kind != expected_kind:
            issues.append(
                _issue("missing_required_role", invalid_message, role=role_name)
            )
    return issues


def _validate_area_count(
    scenario: MaterializedScenario,
) -> list[ScenarioValidationIssue]:
    issues: list[ScenarioValidationIssue] = []
    area_count = len(scenario.topology.areas)
    if area_count != scenario.params.area_count:
        issues.append(
            _issue(
                "topology_contract_invalid",
                "materialized area_count does not match normalized params",
                expected_area_count=scenario.params.area_count,
                actual_area_count=area_count,
            )
        )
    if len(scenario.topology.area_ids_in_order) != area_count:
        issues.append(
            _issue(
                "topology_contract_invalid",
                "topology.area_ids_in_order does not match materialized area count",
            )
        )
    if len(set(scenario.topology.area_ids_in_order)) != len(
        scenario.topology.area_ids_in_order
    ):
        issues.append(
            _issue(
                "topology_contract_invalid",
                "topology.area_ids_in_order contains duplicate area ids",
            )
        )
    return issues


def _validate_entities_and_items(
    scenario: MaterializedScenario,
) -> list[ScenarioValidationIssue]:
    issues: list[ScenarioValidationIssue] = []
    roles = scenario.roles
    hint_source = scenario.entities.get(roles.hint_source_id)
    gate_entity = scenario.entities.get(roles.gate_entity_id)
    required_role_item = scenario.items.get(roles.required_item_id)

    if hint_source is None or hint_source.kind != "hint_source":
        issues.append(
            _issue(
                "entity_binding_invalid",
                "hint source entity is missing or invalid",
                entity_id=roles.hint_source_id,
            )
        )
    if gate_entity is None or gate_entity.kind != "gate":
        issues.append(
            _issue(
                "entity_binding_invalid",
                "gate entity is missing or invalid",
                entity_id=roles.gate_entity_id,
            )
        )
    if required_role_item is None or required_role_item.kind != "required_item":
        issues.append(
            _issue(
                "entity_binding_invalid",
                "required item role is missing or invalid",
                item_id=roles.required_item_id,
            )
        )

    if hint_source is not None and hint_source.area_id != roles.start_area_id:
        issues.append(
            _issue(
                "entity_binding_invalid",
                "hint source is not located in the start area",
                entity_id=roles.hint_source_id,
            )
        )
    if gate_entity is not None and gate_entity.area_id != roles.gate_area_id:
        issues.append(
            _issue(
                "entity_binding_invalid",
                "gate entity is not located in the gate area",
                entity_id=roles.gate_entity_id,
            )
        )

    if (
        required_role_item is not None
        and required_role_item.required_by_gate_entity_id != roles.gate_entity_id
    ):
        issues.append(
            _issue(
                "entity_binding_invalid",
                "required item is not tied to the gate entity",
                item_id=roles.required_item_id,
                entity_id=roles.gate_entity_id,
            )
        )
    return issues


def _validate_goal_and_gate_rules(
    scenario: MaterializedScenario,
) -> list[ScenarioValidationIssue]:
    issues: list[ScenarioValidationIssue] = []
    roles = scenario.roles

    if scenario.goal_rule.type != "enter_area":
        issues.append(
            _issue(
                "goal_rule_invalid",
                "goal rule must be target-entry based",
                goal_type=scenario.goal_rule.type,
            )
        )
    if scenario.goal_rule.target_area_id != roles.target_area_id:
        issues.append(
            _issue(
                "goal_rule_invalid",
                "goal rule does not point to the target area role",
                goal_target_area_id=scenario.goal_rule.target_area_id,
                expected_target_area_id=roles.target_area_id,
            )
        )

    if scenario.gate_rule.from_area_id != roles.gate_area_id:
        issues.append(
            _issue(
                "gate_rule_invalid",
                "gate rule origin does not match the gate area role",
                gate_from_area_id=scenario.gate_rule.from_area_id,
                expected_gate_area_id=roles.gate_area_id,
            )
        )
    if scenario.gate_rule.to_area_id != roles.target_area_id:
        issues.append(
            _issue(
                "gate_rule_invalid",
                "gate rule destination does not match the target area role",
                gate_to_area_id=scenario.gate_rule.to_area_id,
                expected_target_area_id=roles.target_area_id,
            )
        )
    if scenario.gate_rule.gate_entity_id != roles.gate_entity_id:
        issues.append(
            _issue(
                "gate_rule_invalid",
                "gate rule gate entity does not match the gate entity role",
                gate_entity_id=scenario.gate_rule.gate_entity_id,
                expected_gate_entity_id=roles.gate_entity_id,
            )
        )

    gate_required_item = scenario.items.get(scenario.gate_rule.required_item_id)
    if gate_required_item is None or gate_required_item.kind != "required_item":
        issues.append(
            _issue(
                "gate_rule_invalid",
                "gate rule required item is missing or invalid",
                item_id=scenario.gate_rule.required_item_id,
            )
        )
    elif (
        gate_required_item.required_by_gate_entity_id
        != scenario.gate_rule.gate_entity_id
    ):
        issues.append(
            _issue(
                "gate_rule_invalid",
                "gate rule required item is not tied to the gate rule gate entity",
                item_id=scenario.gate_rule.required_item_id,
                gate_entity_id=scenario.gate_rule.gate_entity_id,
            )
        )
    return issues


def _validate_dependency_groups(
    scenario: MaterializedScenario,
) -> list[ScenarioValidationIssue]:
    issues: list[ScenarioValidationIssue] = []
    group_id = scenario.gate_rule.dependency_group_id
    if not group_id:
        return issues

    group = scenario.dependency_groups.get(group_id)
    if group is None:
        issues.append(
            _issue(
                "dependency_group_invalid",
                "gate rule dependency group is missing",
                dependency_group_id=group_id,
            )
        )
        return issues
    if not group.node_ids:
        issues.append(
            _issue(
                "dependency_group_invalid",
                "gate rule dependency group must not be empty",
                dependency_group_id=group_id,
            )
        )

    for item_id in group.node_ids:
        item = scenario.items.get(item_id)
        if item is None or item.kind != "required_item":
            issues.append(
                _issue(
                    "dependency_group_invalid",
                    "dependency group item is missing or invalid",
                    dependency_group_id=group_id,
                    item_id=item_id,
                )
            )
            continue
        if item.required_by_gate_entity_id != scenario.gate_rule.gate_entity_id:
            issues.append(
                _issue(
                    "dependency_group_invalid",
                    "dependency group item is not tied to the gate rule gate entity",
                    dependency_group_id=group_id,
                    item_id=item_id,
                    gate_entity_id=scenario.gate_rule.gate_entity_id,
                )
            )
    return issues


def _validate_progression_contract(
    scenario: MaterializedScenario,
) -> list[ScenarioValidationIssue]:
    issues: list[ScenarioValidationIssue] = []
    roles = scenario.roles
    main_path = list(scenario.topology.main_path_area_ids)
    if not main_path:
        issues.append(
            _issue(
                "topology_contract_invalid",
                "topology main path is missing",
            )
        )
        return issues
    if main_path[0] != roles.start_area_id:
        issues.append(
            _issue(
                "topology_contract_invalid",
                "main path must start at the start area",
                main_path_start=main_path[0],
                expected_start_area_id=roles.start_area_id,
            )
        )
    if main_path[-2:] != [roles.gate_area_id, roles.target_area_id]:
        issues.append(
            _issue(
                "topology_contract_invalid",
                "main path must end with gate -> target",
                main_path_end=main_path[-2:],
                expected_end=[roles.gate_area_id, roles.target_area_id],
            )
        )
    if roles.clue_area_id not in main_path:
        issues.append(
            _issue(
                "topology_contract_invalid",
                "main path does not include the clue area",
                clue_area_id=roles.clue_area_id,
            )
        )
        return issues

    clue_index = main_path.index(roles.clue_area_id)
    gate_index = main_path.index(roles.gate_area_id)
    target_index = main_path.index(roles.target_area_id)
    if not (0 < clue_index < gate_index < target_index):
        issues.append(
            _issue(
                "topology_contract_invalid",
                "main path progression order is invalid",
                clue_index=clue_index,
                gate_index=gate_index,
                target_index=target_index,
            )
        )
    return issues


def _build_static_validation_view(
    scenario: MaterializedScenario,
) -> _ScenarioStaticValidationView:
    dependency_mode, required_item_ids = _resolve_gate_dependency_items(scenario)
    graph = {
        area_id: set(area.connected_area_ids)
        for area_id, area in scenario.topology.areas.items()
    }
    ungated_graph = _remove_edge(
        graph,
        scenario.gate_rule.from_area_id,
        scenario.gate_rule.to_area_id,
    )
    item_source_area_ids: dict[str, tuple[str, ...]] = {}
    for item_id in required_item_ids:
        item = scenario.items.get(item_id)
        source_entity = (
            scenario.entities.get(item.revealed_by_entity_id)
            if item is not None
            else None
        )
        if source_entity is None:
            item_source_area_ids[item_id] = ()
            continue
        item_source_area_ids[item_id] = (source_entity.area_id,)

    return _ScenarioStaticValidationView(
        start_area_id=scenario.roles.start_area_id,
        clue_area_id=scenario.roles.clue_area_id,
        clue_source_id=scenario.roles.clue_source_id,
        revealed_item_id=scenario.roles.revealed_item_id,
        gate_area_id=scenario.gate_rule.from_area_id,
        target_area_id=scenario.goal_rule.target_area_id,
        gate_dependency_mode=dependency_mode,
        required_item_ids=required_item_ids,
        graph=graph,
        ungated_graph=ungated_graph,
        item_source_area_ids=item_source_area_ids,
    )


def _validate_static_clue_support(
    scenario: MaterializedScenario,
    view: _ScenarioStaticValidationView,
) -> list[ScenarioValidationIssue]:
    issues: list[ScenarioValidationIssue] = []
    critical_item = scenario.items.get(view.revealed_item_id)
    clue_source = scenario.entities.get(view.clue_source_id)

    if clue_source is None or clue_source.kind != "clue_source":
        issues.append(
            _issue(
                "critical_clue_support_missing",
                "critical clue support source is missing",
                clue_source_id=view.clue_source_id,
                item_id=view.revealed_item_id,
            )
        )
        return issues

    if clue_source.area_id not in scenario.topology.areas:
        issues.append(
            _issue(
                "critical_clue_binding_invalid",
                "critical clue source area is missing from topology",
                clue_source_id=view.clue_source_id,
                source_area_id=clue_source.area_id,
                item_id=view.revealed_item_id,
            )
        )
        return issues

    if clue_source.area_id != view.clue_area_id:
        issues.append(
            _issue(
                "critical_clue_binding_invalid",
                "critical clue source does not match the clue area role",
                clue_source_id=view.clue_source_id,
                source_area_id=clue_source.area_id,
                expected_clue_area_id=view.clue_area_id,
                item_id=view.revealed_item_id,
            )
        )
        return issues

    if critical_item is None or critical_item.kind != "required_item":
        issues.append(
            _issue(
                "critical_clue_binding_invalid",
                "critical clue item is missing or invalid",
                clue_source_id=view.clue_source_id,
                item_id=view.revealed_item_id,
            )
        )
        return issues

    if not critical_item.revealed_by_entity_id:
        issues.append(
            _issue(
                "critical_clue_support_missing",
                "critical clue item does not declare a reveal source",
                clue_source_id=view.clue_source_id,
                item_id=view.revealed_item_id,
            )
        )
        return issues

    if critical_item.revealed_by_entity_id != view.clue_source_id:
        issues.append(
            _issue(
                "critical_clue_binding_invalid",
                "critical clue item is not bound to the clue source role",
                clue_source_id=view.clue_source_id,
                actual_source_entity_id=critical_item.revealed_by_entity_id,
                item_id=view.revealed_item_id,
            )
        )
        return issues

    if clue_source.reveals_item_id != view.revealed_item_id:
        issues.append(
            _issue(
                "critical_clue_binding_invalid",
                "critical clue source does not reveal the expected item role",
                clue_source_id=view.clue_source_id,
                item_id=view.revealed_item_id,
                actual_revealed_item_id=clue_source.reveals_item_id,
            )
        )
        return issues

    if not _is_reachable(view.ungated_graph, view.start_area_id, clue_source.area_id):
        issues.append(
            _issue(
                "critical_clue_support_unreachable",
                "critical clue support is not reachable before the gated transition",
                clue_source_id=view.clue_source_id,
                source_area_id=clue_source.area_id,
                gate_area_id=view.gate_area_id,
                item_id=view.revealed_item_id,
            )
        )
    return issues


def _validate_static_gameplay(
    scenario: MaterializedScenario,
    view: _ScenarioStaticValidationView,
) -> list[ScenarioValidationIssue]:
    issues: list[ScenarioValidationIssue] = []
    if not _is_reachable(view.graph, view.start_area_id, view.target_area_id):
        issues.append(
            _issue(
                "static_completion_path_missing",
                "completion target is not reachable in the generated topology",
                start_area_id=view.start_area_id,
                target_area_id=view.target_area_id,
            )
        )

    if not _is_reachable(view.ungated_graph, view.start_area_id, view.gate_area_id):
        issues.append(
            _issue(
                "static_dead_end_detected",
                "gate area is not reachable before crossing the gate",
                reason="gate_area_unreachable_before_gate",
                gate_area_id=view.gate_area_id,
            )
        )

    if not _is_reachable(view.ungated_graph, view.start_area_id, view.clue_area_id):
        issues.append(
            _issue(
                "static_dead_end_detected",
                "clue area is not reachable before crossing the gate",
                reason="clue_area_unreachable_before_gate",
                clue_area_id=view.clue_area_id,
            )
        )

    if _is_reachable(view.ungated_graph, view.start_area_id, view.target_area_id):
        issues.append(
            _issue(
                "static_dead_end_detected",
                "completion target must not be reachable without crossing the gate",
                reason="target_reachable_without_gate",
                target_area_id=view.target_area_id,
            )
        )

    reachable_item_ids = [
        item_id
        for item_id in view.required_item_ids
        if any(
            _is_reachable(view.ungated_graph, view.start_area_id, source_area_id)
            for source_area_id in view.item_source_area_ids.get(item_id, ())
        )
    ]
    if view.gate_dependency_mode == "any_of":
        dependency_satisfied = bool(reachable_item_ids)
    else:
        dependency_satisfied = len(reachable_item_ids) == len(view.required_item_ids)

    if not dependency_satisfied:
        issues.append(
            _issue(
                "static_gate_dependency_unsatisfied",
                "gate dependency is not satisfiable before the gated transition",
                dependency_mode=view.gate_dependency_mode,
                required_item_ids=list(view.required_item_ids),
                reachable_item_ids=reachable_item_ids,
                gate_area_id=view.gate_area_id,
            )
        )
    return issues


def _resolve_gate_dependency_items(
    scenario: MaterializedScenario,
) -> tuple[str, tuple[str, ...]]:
    group_id = scenario.gate_rule.dependency_group_id
    if group_id:
        group = scenario.dependency_groups.get(group_id)
        if group is not None and group.node_ids:
            return group.mode, tuple(dict.fromkeys(group.node_ids))
    return "all_of", (scenario.gate_rule.required_item_id,)


def _remove_edge(
    graph: dict[str, set[str]],
    left: str,
    right: str,
) -> dict[str, set[str]]:
    copied = {area_id: set(neighbors) for area_id, neighbors in graph.items()}
    copied.get(left, set()).discard(right)
    copied.get(right, set()).discard(left)
    return copied


def _is_reachable(
    graph: dict[str, set[str]],
    start: str,
    target: str,
) -> bool:
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
