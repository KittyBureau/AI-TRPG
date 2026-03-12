from __future__ import annotations

from collections import deque

import pytest

from backend.app.scenario_bootstrap_adapter import build_scenario_bootstrap_fragment
from backend.app.scenario_bridge import build_scenario_runtime_bridge
from backend.app.scenario_builder import build_materialized_scenario
from backend.app.scenario_templates import normalize_scenario_params
from backend.app.world_presets import (
    TEST_WATCHTOWER_WORLD_ID,
    build_campaign_world_preset,
)


def _dump(model: object) -> object:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    return model


@pytest.fixture
def normalized_params():
    return normalize_scenario_params(
        {"area_count": 7, "layout_type": "branch", "difficulty": "standard"}
    )


@pytest.fixture
def materialized_scenario(normalized_params):
    return build_materialized_scenario(normalized_params)


@pytest.fixture
def runtime_bridge(materialized_scenario):
    return build_scenario_runtime_bridge(materialized_scenario)


@pytest.fixture
def bootstrap_fragment(runtime_bridge):
    return build_scenario_bootstrap_fragment(runtime_bridge)


def _is_reachable(areas: dict[str, dict[str, object]], start: str, target: str) -> bool:
    if start == target:
        return True
    queue = deque([start])
    visited = {start}
    while queue:
        current = queue.popleft()
        for neighbor in sorted(areas[current]["reachable_area_ids"]):
            if neighbor in visited:
                continue
            if neighbor == target:
                return True
            visited.add(neighbor)
            queue.append(neighbor)
    return False


def test_valid_bridged_key_gate_scenario_converts_to_bootstrap_fragment(
    bootstrap_fragment,
) -> None:
    assert bootstrap_fragment.template_id == "key_gate_scenario"
    assert bootstrap_fragment.start_area_id
    assert bootstrap_fragment.clue_area_id
    assert bootstrap_fragment.target_area_id


def test_identical_bridge_input_produces_identical_bootstrap_fragment_output(
    runtime_bridge,
) -> None:
    first = build_scenario_bootstrap_fragment(runtime_bridge)
    second = build_scenario_bootstrap_fragment(runtime_bridge)

    assert _dump(first) == _dump(second)


def test_bootstrap_fragment_preserves_required_runtime_near_semantics(
    bootstrap_fragment,
) -> None:
    assert bootstrap_fragment.start_area_id == "area_start"
    assert bootstrap_fragment.clue_area_id == "area_clue"
    assert bootstrap_fragment.searchable_clue_source.area_id == "area_clue"
    assert bootstrap_fragment.key_item_grant.item_id == "required_item_001"
    assert bootstrap_fragment.key_item_grant.source_interactable_id == "clue_source_001"
    assert bootstrap_fragment.gate.from_area_id == "area_gate"
    assert bootstrap_fragment.gate.to_area_id == "area_target"
    assert bootstrap_fragment.gate.required_item_id == "required_item_001"
    assert bootstrap_fragment.completion.type == "enter_area"
    assert bootstrap_fragment.completion.target_area_id == "area_target"


def test_hint_searchable_source_and_key_item_grant_remain_distinct_roles(
    bootstrap_fragment,
) -> None:
    assert bootstrap_fragment.hint_source.interactable_id == "hint_source_001"
    assert bootstrap_fragment.searchable_clue_source.interactable_id == "clue_source_001"
    assert bootstrap_fragment.key_item_grant.item_id == "required_item_001"
    assert bootstrap_fragment.hint_source.interactable_id != bootstrap_fragment.searchable_clue_source.interactable_id
    assert bootstrap_fragment.searchable_clue_source.interactable_id == bootstrap_fragment.key_item_grant.source_interactable_id


def test_extra_areas_remain_neutral_transit_areas_only(
    bootstrap_fragment,
) -> None:
    transit_areas = [
        area
        for area in bootstrap_fragment.areas.values()
        if area.id not in {"area_start", "area_clue", "area_gate", "area_target"}
    ]

    assert len(transit_areas) == 3
    assert all(area.kind == "transit" for area in transit_areas)


def test_bootstrap_fragment_is_internal_only_and_not_persisted_world_schema(
    bootstrap_fragment,
) -> None:
    payload = _dump(bootstrap_fragment)

    assert "world_id" not in payload
    assert "generator" not in payload
    assert "schema_version" not in payload
    assert "created_at" not in payload
    assert "updated_at" not in payload


def test_broken_bridge_fixture_is_rejected() -> None:
    bridge = build_scenario_runtime_bridge(
        build_materialized_scenario(normalize_scenario_params({}))
    )
    broken = bridge.model_copy(
        update={
            "interactables": {
                key: value
                for key, value in bridge.interactables.items()
                if value.kind != "hint_source"
            }
        }
    )

    with pytest.raises(ValueError, match="hint source"):
        build_scenario_bootstrap_fragment(broken)


def test_bootstrap_fragment_contains_enough_information_for_later_bootstrap_integration(
    bootstrap_fragment,
) -> None:
    payload = _dump(bootstrap_fragment)

    assert len(payload["areas"]) == payload["area_count"]
    assert payload["start_area_id"] in payload["areas"]
    assert payload["clue_area_id"] in payload["areas"]
    assert payload["target_area_id"] in payload["areas"]
    assert payload["gate"]["from_area_id"] in payload["areas"]
    assert payload["gate"]["to_area_id"] in payload["areas"]
    assert payload["completion"]["target_area_id"] == payload["target_area_id"]


def test_fixture_chain_regression_payloads_are_deterministic(
    normalized_params,
    materialized_scenario,
    runtime_bridge,
    bootstrap_fragment,
) -> None:
    assert _dump(normalized_params) == {
        "scenario_template": "key_gate_scenario",
        "theme": "watchtower",
        "area_count": 7,
        "layout_type": "branch",
        "difficulty": "standard",
    }
    assert _dump(materialized_scenario)["topology"]["main_path_area_ids"] == (
        "area_start",
        "area_transit_pre_clue_01",
        "area_clue",
        "area_transit_pre_gate_01",
        "area_gate",
        "area_target",
    )
    assert sorted(_dump(runtime_bridge)["interactables"].keys()) == [
        "clue_source_001",
        "gate_001",
        "hint_source_001",
    ]
    assert _dump(bootstrap_fragment)["key_item_grant"] == {
        "item_id": "required_item_001",
        "source_interactable_id": "clue_source_001",
        "source_area_id": "area_clue",
        "grant_interaction": "search",
    }


def test_bootstrap_fragment_matches_watchtower_baseline_semantics() -> None:
    preset = build_campaign_world_preset(TEST_WATCHTOWER_WORLD_ID)
    assert preset is not None

    fragment = build_scenario_bootstrap_fragment(
        build_scenario_runtime_bridge(
            build_materialized_scenario(normalize_scenario_params({}))
        )
    )

    hint_entities = [
        entity for entity in preset.entities.values() if "hint" in entity.tags
    ]
    clue_entities = [
        entity
        for entity in preset.entities.values()
        if "search" in entity.verbs and entity.state.get("inventory_item_id")
    ]
    gate_entities = [
        entity
        for entity in preset.entities.values()
        if isinstance(entity.state.get("required_item_id"), str)
    ]

    assert preset.start_area_id
    assert hint_entities
    assert clue_entities
    assert gate_entities
    assert fragment.start_area_id
    assert fragment.hint_source.interactable_id
    assert fragment.searchable_clue_source.interactable_id
    assert fragment.key_item_grant.item_id == fragment.gate.required_item_id
    assert fragment.completion.type == "enter_area"
    assert fragment.completion.target_area_id == fragment.target_area_id

    preset_areas = {
        area_id: {
            "reachable_area_ids": list(area.reachable_area_ids),
        }
        for area_id, area in preset.map_data.areas.items()
    }
    fragment_areas = {
        area_id: {
            "reachable_area_ids": list(area.reachable_area_ids),
        }
        for area_id, area in fragment.areas.items()
    }

    assert _is_reachable(preset_areas, preset.start_area_id, clue_entities[0].loc.id)
    assert _is_reachable(fragment_areas, fragment.start_area_id, fragment.clue_area_id)
    assert fragment.gate.from_area_id != fragment.target_area_id
    assert gate_entities[0].state["required_item_id"] == clue_entities[0].state["inventory_item_id"]
