from __future__ import annotations

from collections import deque

import pytest

from backend.app.scenario_builder import build_materialized_scenario
from backend.app.scenario_templates import normalize_scenario_params
from backend.app.scenario_validator import validate_materialized_scenario


def _dump(model: object) -> object:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    return model


def _is_reachable_without_gate(scenario: object) -> bool:
    payload = _dump(scenario)
    roles = payload["roles"]
    topology = payload["topology"]
    gate_rule = payload["gate_rule"]

    graph = {
        area_id: set(area["connected_area_ids"])
        for area_id, area in topology["areas"].items()
    }
    graph[gate_rule["from_area_id"]].discard(gate_rule["to_area_id"])
    graph[gate_rule["to_area_id"]].discard(gate_rule["from_area_id"])

    start = roles["start_area_id"]
    target = roles["target_area_id"]
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


def test_builder_materializes_key_gate_scenario_successfully() -> None:
    params = normalize_scenario_params({})
    scenario = build_materialized_scenario(params)

    assert scenario.template_id == "key_gate_scenario"
    assert scenario.params == params
    assert len(scenario.topology.areas) == params.area_count
    assert scenario.goal_rule.type == "enter_area"


def test_identical_normalized_params_produce_identical_structure() -> None:
    params = normalize_scenario_params(
        {
            "theme": "watchtower",
            "area_count": 6,
            "layout_type": "branch",
            "difficulty": "easy",
        }
    )

    first = build_materialized_scenario(params)
    second = build_materialized_scenario(params)

    assert _dump(first) == _dump(second)


def test_different_allowed_params_change_structure_in_expected_deterministic_ways() -> None:
    linear = build_materialized_scenario(
        normalize_scenario_params(
            {"area_count": 5, "layout_type": "linear", "difficulty": "easy"}
        )
    )
    branch_layout = build_materialized_scenario(
        normalize_scenario_params(
            {"area_count": 5, "layout_type": "branch", "difficulty": "easy"}
        )
    )
    easy = build_materialized_scenario(
        normalize_scenario_params(
            {"area_count": 5, "layout_type": "linear", "difficulty": "easy"}
        )
    )
    standard = build_materialized_scenario(
        normalize_scenario_params(
            {"area_count": 5, "layout_type": "linear", "difficulty": "standard"}
        )
    )

    assert linear.topology.branch_area_ids == ()
    assert branch_layout.topology.branch_area_ids == ("area_transit_branch_01",)
    assert easy.topology.main_path_area_ids == (
        "area_start",
        "area_clue",
        "area_transit_pre_gate_01",
        "area_gate",
        "area_target",
    )
    assert standard.topology.main_path_area_ids == (
        "area_start",
        "area_transit_pre_clue_01",
        "area_clue",
        "area_gate",
        "area_target",
    )


@pytest.mark.parametrize("area_count", [4, 5, 6, 7, 8])
def test_builder_respects_area_count_bounds(area_count: int) -> None:
    scenario = build_materialized_scenario(
        normalize_scenario_params({"area_count": area_count})
    )

    assert len(scenario.topology.areas) == area_count
    assert len(scenario.topology.area_ids_in_order) == area_count


def test_extra_areas_are_neutral_transit_areas_only() -> None:
    scenario = build_materialized_scenario(
        normalize_scenario_params({"area_count": 8, "layout_type": "branch"})
    )
    role_area_ids = {
        scenario.roles.start_area_id,
        scenario.roles.clue_area_id,
        scenario.roles.gate_area_id,
        scenario.roles.target_area_id,
    }

    transit_areas = [
        area
        for area_id, area in scenario.topology.areas.items()
        if area_id not in role_area_ids
    ]

    assert len(transit_areas) == 4
    assert all(area.kind == "transit" for area in transit_areas)


def test_required_roles_exist_in_materialized_scenario() -> None:
    scenario = build_materialized_scenario(normalize_scenario_params({}))

    assert scenario.roles.start_area_id in scenario.topology.areas
    assert scenario.roles.clue_area_id in scenario.topology.areas
    assert scenario.roles.gate_area_id in scenario.topology.areas
    assert scenario.roles.target_area_id in scenario.topology.areas
    assert scenario.roles.hint_source_id in scenario.entities
    assert scenario.roles.clue_source_id in scenario.entities
    assert scenario.roles.gate_entity_id in scenario.entities
    assert scenario.roles.required_item_id in scenario.items


def test_progression_order_is_start_to_clue_to_gate_to_target() -> None:
    scenario = build_materialized_scenario(
        normalize_scenario_params({"area_count": 8, "layout_type": "branch"})
    )
    main_path = list(scenario.topology.main_path_area_ids)

    assert main_path[0] == scenario.roles.start_area_id
    assert main_path.index(scenario.roles.clue_area_id) < main_path.index(
        scenario.roles.gate_area_id
    )
    assert main_path.index(scenario.roles.gate_area_id) < main_path.index(
        scenario.roles.target_area_id
    )
    assert scenario.entities[scenario.roles.clue_source_id].grants_item_id == scenario.roles.required_item_id
    assert scenario.entities[scenario.roles.gate_entity_id].requires_item_id == scenario.roles.required_item_id


def test_validator_accepts_valid_generated_scenario() -> None:
    scenario = build_materialized_scenario(
        normalize_scenario_params({"area_count": 7, "layout_type": "branch"})
    )

    result = validate_materialized_scenario(scenario)

    assert result.ok is True
    assert result.template_id == "key_gate_scenario"
    assert result.checked_area_count == 7


def test_validator_rejects_deliberately_broken_scenario_fixture() -> None:
    scenario = build_materialized_scenario(normalize_scenario_params({}))
    broken = scenario.model_copy(
        update={
            "goal_rule": scenario.goal_rule.model_copy(
                update={"target_area_id": scenario.roles.clue_area_id}
            )
        }
    )

    with pytest.raises(ValueError, match="goal rule"):
        validate_materialized_scenario(broken)


def test_target_is_not_reachable_without_crossing_gate() -> None:
    scenario = build_materialized_scenario(
        normalize_scenario_params({"area_count": 8, "layout_type": "branch"})
    )

    assert _is_reachable_without_gate(scenario) is False


def test_goal_rule_is_target_entry_based() -> None:
    scenario = build_materialized_scenario(normalize_scenario_params({}))

    assert scenario.goal_rule.type == "enter_area"
    assert scenario.goal_rule.target_area_id == scenario.roles.target_area_id


def test_materialized_scenario_does_not_require_narrative_or_runtime_payloads() -> None:
    scenario = build_materialized_scenario(normalize_scenario_params({}))
    payload = _dump(scenario)

    assert "world" not in payload
    assert "bootstrap" not in payload
    assert "goal_text" not in payload
    for area in payload["topology"]["areas"].values():
        assert "description" not in area
        assert "name" not in area
