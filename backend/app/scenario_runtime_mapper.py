from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from backend.app.scenario_bootstrap_adapter import build_scenario_bootstrap_fragment
from backend.app.scenario_bridge import build_scenario_runtime_bridge
from backend.app.scenario_builder import build_materialized_scenario
from backend.app.scenario_templates import normalize_scenario_params
from backend.domain.models import Entity, EntityLocation, MapArea, MapData, RuntimeItemStack
from backend.domain.scenario_bootstrap_models import ScenarioBootstrapFragment
from backend.domain.world_models import World

SCENARIO_GENERATOR_ID = "playable_scenario_v0"
SCENARIO_MODE = "playable_scenario"


@dataclass(frozen=True)
class ScenarioRuntimeBootstrapPayload:
    start_area_id: str
    goal_text: str
    map_data: MapData
    items: Dict[str, RuntimeItemStack]
    entities: Dict[str, Entity]
    fragment: ScenarioBootstrapFragment


def build_runtime_bootstrap_from_world(
    world: World,
) -> Optional[ScenarioRuntimeBootstrapPayload]:
    fragment = build_scenario_bootstrap_fragment_for_world(world)
    if fragment is None:
        return None
    return build_runtime_bootstrap_from_fragment(fragment)


def build_runtime_bootstrap_from_fragment(
    fragment: ScenarioBootstrapFragment,
) -> ScenarioRuntimeBootstrapPayload:
    return ScenarioRuntimeBootstrapPayload(
        start_area_id=fragment.start_area_id,
        goal_text="Find the required item and enter the target area.",
        map_data=_build_map_data(fragment),
        items={},
        entities=_build_entities(fragment),
        fragment=fragment,
    )


def build_scenario_bootstrap_fragment_for_world(
    world: World,
) -> Optional[ScenarioBootstrapFragment]:
    if not _is_supported_scenario_world(world):
        return None
    params = normalize_scenario_params(world.generator.params)
    scenario = build_materialized_scenario(params)
    bridge = build_scenario_runtime_bridge(scenario)
    return build_scenario_bootstrap_fragment(bridge)


def is_scenario_generator_world(world: World) -> bool:
    generator = world.generator
    if not generator.id.strip():
        return False
    if generator.id.strip() != SCENARIO_GENERATOR_ID:
        return False
    if not isinstance(generator.params, dict):
        return False
    return generator.params.get("mode") == SCENARIO_MODE


def _is_supported_scenario_world(world: World) -> bool:
    if not is_scenario_generator_world(world):
        return False
    return world.generator.params.get("template_id") == "key_gate_scenario"


def _build_map_data(fragment: ScenarioBootstrapFragment) -> MapData:
    return MapData(
        areas={
            area_id: MapArea(
                id=area.id,
                name=area.id,
                description="",
                reachable_area_ids=list(area.reachable_area_ids),
            )
            for area_id, area in fragment.areas.items()
        },
        connections=[],
    )


def _build_entities(fragment: ScenarioBootstrapFragment) -> Dict[str, Entity]:
    hint_source = fragment.hint_source
    clue_source = fragment.searchable_clue_source
    revealed_item = fragment.revealed_item
    gate = fragment.gate
    key_stack_id = _build_scenario_key_stack_id(
        clue_source.interactable_id,
        revealed_item.item_id,
    )

    return {
        hint_source.interactable_id: Entity(
            id=hint_source.interactable_id,
            kind="npc",
            label=hint_source.interactable_id,
            tags=["npc", "hint"],
            loc=EntityLocation(type="area", id=hint_source.area_id),
            verbs=["inspect", "talk"],
            state={"hint": "Search the clue source before the gate."},
            props={},
        ),
        clue_source.interactable_id: Entity(
            id=clue_source.interactable_id,
            kind="container",
            label=clue_source.interactable_id,
            tags=["clue", "search_spot", "stash"],
            loc=EntityLocation(type="area", id=clue_source.area_id),
            verbs=["inspect", "search"],
            state={
                "opened": True,
                "search_loot_stack_id": key_stack_id,
                "search_loot_definition_id": revealed_item.item_id,
                "search_loot_label": revealed_item.item_id,
                "search_loot_tags": ["key"],
                "search_loot_stackable": False,
            },
            props={},
        ),
        gate.interactable_id: Entity(
            id=gate.interactable_id,
            kind="object",
            label=gate.interactable_id,
            tags=["door", "gate", "locked"],
            loc=EntityLocation(type="area", id=gate.area_id),
            verbs=["inspect", "open"],
            state={"locked": True},
            props={},
        ),
    }


def _build_scenario_key_stack_id(
    source_interactable_id: str,
    item_id: str,
) -> str:
    return f"stk_{source_interactable_id}_{item_id}"
