from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from backend.domain.models import Entity, EntityLocation, MapArea, MapData, RuntimeItemStack
from backend.domain.world_models import World, WorldGenerator, stable_seed_from_world_id, stable_world_timestamp

TEST_WATCHTOWER_WORLD_ID = "test_watchtower_world"
TEST_WATCHTOWER_START_AREA_ID = "village_gate"
TEST_WATCHTOWER_TARGET_AREA_ID = "watchtower_inside"
TEST_WATCHTOWER_GATE_FROM_AREA_ID = "watchtower_entrance"
TEST_WATCHTOWER_GATE_ITEM_ID = "tower_key"
# Internal development preset for the scenario-generator v0 runtime path.
DEV_KEY_GATE_SCENARIO_WORLD_ID = "dev_key_gate_scenario_world"


@dataclass(frozen=True)
class CampaignWorldPreset:
    start_area_id: str
    goal_text: str
    map_data: MapData
    items: Dict[str, RuntimeItemStack]
    entities: Dict[str, Entity]


def build_world_preset(world_id: str) -> Optional[World]:
    normalized_world_id = world_id.strip()
    if normalized_world_id == DEV_KEY_GATE_SCENARIO_WORLD_ID:
        now = stable_world_timestamp(normalized_world_id)
        return World(
            world_id=normalized_world_id,
            name="Dev Key Gate Scenario World",
            seed=stable_seed_from_world_id(normalized_world_id),
            world_description=(
                "A scenario-backed development preset for validating the key-gate runtime path."
            ),
            objective="Find the required item and enter the target area.",
            start_area="area_start",
            generator=WorldGenerator(
                id="playable_scenario_v0",
                version="1",
                params={
                    "mode": "playable_scenario",
                    "template_id": "key_gate_scenario",
                    "template_version": "v0",
                    "theme": "watchtower",
                    "area_count": 4,
                    "layout_type": "linear",
                    "difficulty": "easy",
                },
            ),
            schema_version="1",
            created_at=now,
            updated_at=now,
        )
    if normalized_world_id != TEST_WATCHTOWER_WORLD_ID:
        return None
    now = stable_world_timestamp(normalized_world_id)
    return World(
        world_id=normalized_world_id,
        name="Test Watchtower World",
        seed=stable_seed_from_world_id(normalized_world_id),
        world_description=(
            "A fixed smoke-test world with a village approach, an old hut, and a locked watchtower."
        ),
        objective="Find the tower key in the old hut and enter the watchtower.",
        start_area=TEST_WATCHTOWER_START_AREA_ID,
        generator=WorldGenerator(
            id="static_test_world",
            version="1",
            params={"preset_id": normalized_world_id, "content_mode": "fixed"},
        ),
        schema_version="1",
        created_at=now,
        updated_at=now,
    )


def list_world_presets() -> list[World]:
    preset_ids = [
        DEV_KEY_GATE_SCENARIO_WORLD_ID,
        TEST_WATCHTOWER_WORLD_ID,
    ]
    return [
        preset
        for preset in (build_world_preset(preset_id) for preset_id in preset_ids)
        if preset is not None
    ]


def build_campaign_world_preset(world_id: str) -> Optional[CampaignWorldPreset]:
    normalized_world_id = world_id.strip()
    if normalized_world_id != TEST_WATCHTOWER_WORLD_ID:
        return None
    return CampaignWorldPreset(
        start_area_id=TEST_WATCHTOWER_START_AREA_ID,
        goal_text="Find the tower key in the old hut and enter the watchtower.",
        map_data=MapData(
            areas={
                "village_gate": MapArea(
                    id="village_gate",
                    name="Village Gate",
                    description="A weathered gate faces the abandoned watchtower road.",
                    reachable_area_ids=["village_square"],
                ),
                "village_square": MapArea(
                    id="village_square",
                    name="Village Square",
                    description="An empty square where the hut path and forest path split.",
                    reachable_area_ids=["village_gate", "old_hut", "forest_path"],
                ),
                "old_hut": MapArea(
                    id="old_hut",
                    name="Old Hut",
                    description="A dusty hut with a loose floorboard and signs of hurried departure.",
                    reachable_area_ids=["village_square"],
                ),
                "forest_path": MapArea(
                    id="forest_path",
                    name="Forest Path",
                    description="A narrow path climbs toward the sealed watchtower entrance.",
                    reachable_area_ids=["village_square", "watchtower_entrance"],
                ),
                "watchtower_entrance": MapArea(
                    id="watchtower_entrance",
                    name="Watchtower Entrance",
                    description="A heavy wooden tower door blocks the way inside.",
                    reachable_area_ids=["forest_path", "watchtower_inside"],
                ),
                "watchtower_inside": MapArea(
                    id="watchtower_inside",
                    name="Watchtower Interior",
                    description="The silent watch room confirms the objective is complete.",
                    reachable_area_ids=["watchtower_entrance"],
                ),
            },
            connections=[],
        ),
        items={},
        entities={
            "npc_village_guard": Entity(
                id="npc_village_guard",
                kind="npc",
                label="Village Guard",
                tags=["npc", "guard", "hint"],
                loc=EntityLocation(type="area", id="village_gate"),
                verbs=["inspect", "talk"],
                state={
                    "hint": "The watchtower key was left in the old hut near the square."
                },
                props={},
            ),
            "old_hut_clue": Entity(
                id="old_hut_clue",
                kind="object",
                label="Loose Floorboard",
                tags=["clue", "search_spot"],
                loc=EntityLocation(type="area", id="old_hut"),
                verbs=["inspect", "search"],
                state={
                    "hint": "Something small was hidden here: the tower key.",
                    "inventory_item_id": TEST_WATCHTOWER_GATE_ITEM_ID,
                    "inventory_quantity": 1,
                    "inventory_granted": False,
                },
                props={},
            ),
            "watchtower_door": Entity(
                id="watchtower_door",
                kind="object",
                label="Watchtower Door",
                tags=["door", "gate", "locked"],
                loc=EntityLocation(type="area", id="watchtower_entrance"),
                verbs=["inspect", "open"],
                state={
                    "locked": True,
                    "required_item_id": TEST_WATCHTOWER_GATE_ITEM_ID,
                },
                props={},
            ),
        },
    )


def required_item_for_move(
    world_id: str,
    from_area_id: str,
    to_area_id: str,
) -> Optional[str]:
    normalized_world_id = world_id.strip()
    if normalized_world_id != TEST_WATCHTOWER_WORLD_ID:
        return None
    if (
        from_area_id == TEST_WATCHTOWER_GATE_FROM_AREA_ID
        and to_area_id == TEST_WATCHTOWER_TARGET_AREA_ID
    ):
        return TEST_WATCHTOWER_GATE_ITEM_ID
    return None


def is_goal_area(world_id: str, area_id: str) -> bool:
    return world_id.strip() == TEST_WATCHTOWER_WORLD_ID and area_id == TEST_WATCHTOWER_TARGET_AREA_ID
