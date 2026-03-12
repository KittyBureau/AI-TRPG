from __future__ import annotations

import pytest

from backend.app.scenario_bridge import build_scenario_runtime_bridge
from backend.app.scenario_builder import build_materialized_scenario
from backend.app.scenario_templates import normalize_scenario_params


def _dump(model: object) -> object:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    return model


def test_valid_materialized_key_gate_scenario_can_be_bridged() -> None:
    scenario = build_materialized_scenario(normalize_scenario_params({}))

    bridge = build_scenario_runtime_bridge(scenario)

    assert bridge.template_id == "key_gate_scenario"
    assert bridge.start_area_id == scenario.roles.start_area_id
    assert bridge.clue_area_id == scenario.roles.clue_area_id
    assert bridge.target_area_id == scenario.roles.target_area_id


def test_identical_materialized_scenarios_produce_identical_bridge_output() -> None:
    params = normalize_scenario_params(
        {"area_count": 7, "layout_type": "branch", "difficulty": "standard"}
    )
    first = build_scenario_runtime_bridge(build_materialized_scenario(params))
    second = build_scenario_runtime_bridge(build_materialized_scenario(params))

    assert _dump(first) == _dump(second)


def test_bridge_preserves_required_runtime_facing_semantics() -> None:
    scenario = build_materialized_scenario(
        normalize_scenario_params({"area_count": 8, "layout_type": "branch"})
    )
    bridge = build_scenario_runtime_bridge(scenario)

    assert bridge.start_area_id == "area_start"
    assert bridge.clue_area_id == "area_clue"
    assert bridge.key_item.item_id == "required_item_001"
    assert bridge.key_item.source_interactable_id == "clue_source_001"
    assert bridge.gate.from_area_id == "area_gate"
    assert bridge.gate.to_area_id == "area_target"
    assert bridge.gate.required_item_id == "required_item_001"
    assert bridge.completion.type == "enter_area"
    assert bridge.completion.target_area_id == "area_target"


def test_hint_source_and_searchable_clue_source_remain_distinct_in_bridge_output() -> None:
    bridge = build_scenario_runtime_bridge(
        build_materialized_scenario(normalize_scenario_params({}))
    )

    assert bridge.interactables["hint_source_001"].kind == "hint_source"
    assert bridge.interactables["clue_source_001"].kind == "searchable_clue_source"
    assert bridge.interactables["hint_source_001"].id != bridge.interactables["clue_source_001"].id


def test_extra_areas_remain_neutral_transit_areas_only_in_bridge_output() -> None:
    bridge = build_scenario_runtime_bridge(
        build_materialized_scenario(
            normalize_scenario_params({"area_count": 8, "layout_type": "branch"})
        )
    )

    transit_areas = [
        area
        for area in bridge.areas.values()
        if area.id not in {"area_start", "area_clue", "area_gate", "area_target"}
    ]
    assert len(transit_areas) == 4
    assert all(area.kind == "transit" for area in transit_areas)


def test_bridge_output_is_internal_and_not_a_persisted_world_schema() -> None:
    bridge = build_scenario_runtime_bridge(
        build_materialized_scenario(normalize_scenario_params({}))
    )
    payload = _dump(bridge)

    assert "world_id" not in payload
    assert "schema_version" not in payload
    assert "generator" not in payload
    assert "created_at" not in payload
    assert "updated_at" not in payload


def test_bridge_rejects_deliberately_broken_materialized_scenario() -> None:
    scenario = build_materialized_scenario(normalize_scenario_params({}))
    broken = scenario.model_copy(
        update={
            "entities": {
                key: value
                for key, value in scenario.entities.items()
                if key != scenario.roles.clue_source_id
            }
        }
    )

    with pytest.raises(ValueError, match="clue source"):
        build_scenario_runtime_bridge(broken)


def test_bridge_output_has_no_runtime_wiring_or_side_effect_fields() -> None:
    bridge = build_scenario_runtime_bridge(
        build_materialized_scenario(
            normalize_scenario_params({"area_count": 5, "layout_type": "linear"})
        )
    )
    payload = _dump(bridge)

    assert "bootstrap" not in payload
    assert "world" not in payload
    assert "campaign" not in payload
    assert "api" not in payload
