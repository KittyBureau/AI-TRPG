from __future__ import annotations

from collections import deque

from backend.app.scenario_templates import get_scenario_template
from backend.domain.scenario_models import (
    MaterializedScenario,
    ScenarioValidationResult,
)


def validate_materialized_scenario(
    scenario: MaterializedScenario,
) -> ScenarioValidationResult:
    template = get_scenario_template(scenario.template_id)

    if scenario.template_version != template.template_version:
        raise ValueError("scenario template_version does not match the template registry")
    if scenario.params.scenario_template != template.template_id:
        raise ValueError("scenario params do not match the materialized template_id")

    _validate_required_roles(scenario)
    _validate_area_count(scenario)
    _validate_entities_and_items(scenario)
    _validate_goal_and_gate_rules(scenario)
    _validate_progression(scenario)

    return ScenarioValidationResult(
        ok=True,
        template_id=scenario.template_id,
        checked_area_count=len(scenario.topology.areas),
    )


def _validate_required_roles(scenario: MaterializedScenario) -> None:
    roles = scenario.roles
    required_values = {
        "start_area_id": roles.start_area_id,
        "hint_source_id": roles.hint_source_id,
        "clue_area_id": roles.clue_area_id,
        "clue_source_id": roles.clue_source_id,
        "granted_item_id": roles.granted_item_id,
        "gate_area_id": roles.gate_area_id,
        "gate_entity_id": roles.gate_entity_id,
        "required_item_id": roles.required_item_id,
        "target_area_id": roles.target_area_id,
    }
    for label, value in required_values.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"missing required role value: {label}")

    area_ids = set(scenario.topology.areas.keys())
    if roles.start_area_id not in area_ids:
        raise ValueError("start area role is missing from topology")
    if roles.clue_area_id not in area_ids:
        raise ValueError("clue area role is missing from topology")
    if roles.gate_area_id not in area_ids:
        raise ValueError("gate area role is missing from topology")
    if roles.target_area_id not in area_ids:
        raise ValueError("target area role is missing from topology")

    if scenario.topology.areas[roles.start_area_id].kind != "start":
        raise ValueError("start area role does not point to a start area")
    if scenario.topology.areas[roles.clue_area_id].kind != "clue":
        raise ValueError("clue area role does not point to a clue area")
    if scenario.topology.areas[roles.gate_area_id].kind != "gate":
        raise ValueError("gate area role does not point to a gate area")
    if scenario.topology.areas[roles.target_area_id].kind != "target":
        raise ValueError("target area role does not point to a target area")


def _validate_area_count(scenario: MaterializedScenario) -> None:
    area_count = len(scenario.topology.areas)
    if area_count != scenario.params.area_count:
        raise ValueError("materialized area_count does not match normalized params")
    if len(scenario.topology.area_ids_in_order) != area_count:
        raise ValueError("topology.area_ids_in_order does not match materialized area count")
    if len(set(scenario.topology.area_ids_in_order)) != len(scenario.topology.area_ids_in_order):
        raise ValueError("topology.area_ids_in_order contains duplicate area ids")


def _validate_entities_and_items(scenario: MaterializedScenario) -> None:
    roles = scenario.roles
    hint_source = scenario.entities.get(roles.hint_source_id)
    clue_source = scenario.entities.get(roles.clue_source_id)
    gate_entity = scenario.entities.get(roles.gate_entity_id)
    required_item = scenario.items.get(roles.required_item_id)

    if hint_source is None or hint_source.kind != "hint_source":
        raise ValueError("hint source entity is missing or invalid")
    if clue_source is None or clue_source.kind != "clue_source":
        raise ValueError("clue source entity is missing or invalid")
    if gate_entity is None or gate_entity.kind != "gate":
        raise ValueError("gate entity is missing or invalid")
    if required_item is None or required_item.kind != "required_item":
        raise ValueError("required item role is missing or invalid")

    if hint_source.area_id != roles.start_area_id:
        raise ValueError("hint source is not located in the start area")
    if clue_source.area_id != roles.clue_area_id:
        raise ValueError("clue source is not located in the clue area")
    if gate_entity.area_id != roles.gate_area_id:
        raise ValueError("gate entity is not located in the gate area")

    if clue_source.grants_item_id != roles.granted_item_id:
        raise ValueError("clue source does not grant the required key item role")
    if gate_entity.requires_item_id != roles.required_item_id:
        raise ValueError("gate entity does not require the expected key item role")
    if required_item.granted_by_entity_id != roles.clue_source_id:
        raise ValueError("required item is not granted by the clue source")
    if required_item.required_by_gate_entity_id != roles.gate_entity_id:
        raise ValueError("required item is not tied to the gate entity")


def _validate_goal_and_gate_rules(scenario: MaterializedScenario) -> None:
    roles = scenario.roles
    if scenario.goal_rule.type != "enter_area":
        raise ValueError("goal rule must be target-entry based")
    if scenario.goal_rule.target_area_id != roles.target_area_id:
        raise ValueError("goal rule does not point to the target area role")

    if scenario.gate_rule.from_area_id != roles.gate_area_id:
        raise ValueError("gate rule origin does not match the gate area role")
    if scenario.gate_rule.to_area_id != roles.target_area_id:
        raise ValueError("gate rule destination does not match the target area role")
    if scenario.gate_rule.required_item_id != roles.required_item_id:
        raise ValueError("gate rule required item does not match the required item role")
    if scenario.gate_rule.gate_entity_id != roles.gate_entity_id:
        raise ValueError("gate rule gate entity does not match the gate entity role")


def _validate_progression(scenario: MaterializedScenario) -> None:
    roles = scenario.roles
    main_path = list(scenario.topology.main_path_area_ids)
    if not main_path:
        raise ValueError("topology main path is missing")
    if main_path[0] != roles.start_area_id:
        raise ValueError("main path must start at the start area")
    if main_path[-2:] != [roles.gate_area_id, roles.target_area_id]:
        raise ValueError("main path must end with gate -> target")
    if roles.clue_area_id not in main_path:
        raise ValueError("main path does not include the clue area")

    clue_index = main_path.index(roles.clue_area_id)
    gate_index = main_path.index(roles.gate_area_id)
    target_index = main_path.index(roles.target_area_id)
    if not (0 < clue_index < gate_index < target_index):
        raise ValueError("main path progression order is invalid")

    graph = {
        area_id: set(area.connected_area_ids)
        for area_id, area in scenario.topology.areas.items()
    }
    if not _is_reachable(graph, roles.start_area_id, roles.clue_area_id):
        raise ValueError("clue area is not reachable from the start area")
    if not _is_reachable(graph, roles.start_area_id, roles.gate_area_id):
        raise ValueError("gate area is not reachable from the start area")
    if not _is_reachable(graph, roles.start_area_id, roles.target_area_id):
        raise ValueError("target area is not reachable in the materialized topology")

    ungated_graph = _remove_edge(
        graph,
        scenario.gate_rule.from_area_id,
        scenario.gate_rule.to_area_id,
    )
    if not _is_reachable(ungated_graph, roles.start_area_id, roles.clue_area_id):
        raise ValueError("clue area must remain reachable without crossing the gate")
    if not _is_reachable(ungated_graph, roles.start_area_id, roles.gate_area_id):
        raise ValueError("gate area must be reachable before crossing the gate")
    if _is_reachable(ungated_graph, roles.start_area_id, roles.target_area_id):
        raise ValueError("target area must not be reachable without crossing the gate")


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
