from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from backend.app.turn_service import TurnService
from backend.app.world_presets import (
    DEV_KEY_GATE_SCENARIO_WORLD_ID,
    TEST_WATCHTOWER_WORLD_ID,
)
from backend.domain.world_models import World, WorldGenerator, stable_world_timestamp
from backend.infra.file_repo import FileRepo


class _ScenarioRuntimeLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        token = user_input.strip()
        if token == "TALK_HINT":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_hint_talk",
                        "tool": "scene_action",
                        "args": {
                            "actor_id": "pc_001",
                            "action": "talk",
                            "target_id": "hint_source_001",
                            "params": {},
                        },
                    }
                ],
            }
        if token == "MOVE_TO_CLUE":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_move_clue",
                        "tool": "move",
                        "args": {"actor_id": "pc_001", "to_area_id": "area_clue"},
                    }
                ],
            }
        if token == "MOVE_TO_GATE":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_move_gate",
                        "tool": "move",
                        "args": {"actor_id": "pc_001", "to_area_id": "area_gate"},
                    }
                ],
            }
        if token == "SEARCH_CLUE":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_search_clue",
                        "tool": "scene_action",
                        "args": {
                            "actor_id": "pc_001",
                            "action": "search",
                            "target_id": "clue_source_001",
                            "params": {},
                        },
                    }
                ],
            }
        if token == "ENTER_TARGET":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_enter_target",
                        "tool": "move",
                        "args": {"actor_id": "pc_001", "to_area_id": "area_target"},
                    }
                ],
            }
        return {
            "assistant_text": "No action.",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }


def _save_scenario_world(
    repo: FileRepo,
    *,
    world_id: str,
    area_count: int,
    layout_type: str,
    difficulty: str,
) -> None:
    repo.save_world(
        World(
            world_id=world_id,
            name=world_id,
            seed=1,
            world_description="",
            objective="",
            start_area="area_start",
            generator=WorldGenerator(
                id="playable_scenario_v0",
                version="1",
                params={
                    "mode": "playable_scenario",
                    "template_id": "key_gate_scenario",
                    "template_version": "v0",
                    "theme": "watchtower",
                    "area_count": area_count,
                    "layout_type": layout_type,
                    "difficulty": difficulty,
                },
            ),
            schema_version="1",
            created_at=stable_world_timestamp(world_id),
            updated_at=stable_world_timestamp(world_id),
        )
    )


def _save_non_supported_metadata_world(
    repo: FileRepo,
    *,
    world_id: str,
    generator_id: str,
    params: dict[str, object],
) -> None:
    repo.save_world(
        World(
            world_id=world_id,
            name=world_id,
            seed=1,
            world_description="",
            objective="",
            start_area="area_001",
            generator=WorldGenerator(
                id=generator_id,
                version="1",
                params=params,
            ),
            schema_version="1",
            created_at=stable_world_timestamp(world_id),
            updated_at=stable_world_timestamp(world_id),
        )
    )


def test_scenario_metadata_world_bootstraps_playable_campaign(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    _save_scenario_world(
        repo,
        world_id="scenario_world_bootstrap",
        area_count=6,
        layout_type="branch",
        difficulty="easy",
    )
    service = TurnService(repo)

    campaign_id = service.create_campaign(
        world_id="scenario_world_bootstrap",
        map_id="map_generated",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )
    campaign = repo.get_campaign(campaign_id)

    assert campaign.actors["pc_001"].position == "area_start"
    assert sorted(campaign.entities.keys()) == [
        "clue_source_001",
        "gate_001",
        "hint_source_001",
    ]
    assert "area_start" in campaign.map.areas
    assert "area_clue" in campaign.map.areas
    assert "area_gate" in campaign.map.areas
    assert "area_target" in campaign.map.areas
    assert campaign.goal.text == "Find the required item and enter the target area."


def test_scenario_metadata_world_is_playable_through_real_runtime_path(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    _save_scenario_world(
        repo,
        world_id="scenario_world_smoke",
        area_count=4,
        layout_type="linear",
        difficulty="easy",
    )
    service = TurnService(repo)
    service.llm = _ScenarioRuntimeLLM()

    campaign_id = service.create_campaign(
        world_id="scenario_world_smoke",
        map_id="map_generated",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )

    talk = service.submit_turn(campaign_id, "TALK_HINT")
    assert talk["applied_actions"][0]["tool"] == "scene_action"

    move_to_clue = service.submit_turn(campaign_id, "MOVE_TO_CLUE")
    assert move_to_clue["state_summary"]["active_area_id"] == "area_clue"

    move_to_gate = service.submit_turn(campaign_id, "MOVE_TO_GATE")
    assert move_to_gate["state_summary"]["active_area_id"] == "area_gate"

    blocked = service.submit_turn(campaign_id, "ENTER_TARGET")
    assert blocked["applied_actions"] == []
    assert blocked["tool_feedback"]["failed_calls"][0]["reason"] == "missing_required_item"

    service.submit_turn(campaign_id, "MOVE_TO_CLUE")
    search = service.submit_turn(campaign_id, "SEARCH_CLUE")
    assert search["applied_actions"][0]["tool"] == "scene_action"
    assert search["state_summary"]["active_actor_inventory"] == {"required_item_001": 1}

    service.submit_turn(campaign_id, "MOVE_TO_GATE")
    entered = service.submit_turn(campaign_id, "ENTER_TARGET")
    assert entered["applied_actions"][0]["tool"] == "move"
    assert entered["state_summary"]["active_area_id"] == "area_target"

    campaign = repo.get_campaign(campaign_id)
    assert campaign.goal.status == "completed"
    assert campaign.lifecycle.ended is True
    assert campaign.lifecycle.reason == "goal_achieved"


def test_identical_generator_params_produce_stable_runtime_bootstrap_behavior(
    tmp_path: Path,
) -> None:
    repo = FileRepo(tmp_path / "storage")
    _save_scenario_world(
        repo,
        world_id="scenario_world_a",
        area_count=7,
        layout_type="branch",
        difficulty="standard",
    )
    _save_scenario_world(
        repo,
        world_id="scenario_world_b",
        area_count=7,
        layout_type="branch",
        difficulty="standard",
    )
    service = TurnService(repo)

    campaign_a = repo.get_campaign(
        service.create_campaign(
            world_id="scenario_world_a",
            map_id="map_generated",
            party_character_ids=["pc_001"],
            active_actor_id="pc_001",
        )
    )
    campaign_b = repo.get_campaign(
        service.create_campaign(
            world_id="scenario_world_b",
            map_id="map_generated",
            party_character_ids=["pc_001"],
            active_actor_id="pc_001",
        )
    )

    areas_a = {
        area_id: list(area.reachable_area_ids)
        for area_id, area in sorted(campaign_a.map.areas.items())
    }
    areas_b = {
        area_id: list(area.reachable_area_ids)
        for area_id, area in sorted(campaign_b.map.areas.items())
    }
    entities_a = {
        entity_id: {
            "kind": entity.kind,
            "loc": entity.loc.id,
            "verbs": list(entity.verbs),
            "state": dict(entity.state),
        }
        for entity_id, entity in sorted(campaign_a.entities.items())
    }
    entities_b = {
        entity_id: {
            "kind": entity.kind,
            "loc": entity.loc.id,
            "verbs": list(entity.verbs),
            "state": dict(entity.state),
        }
        for entity_id, entity in sorted(campaign_b.entities.items())
    }

    assert campaign_a.goal.text == campaign_b.goal.text
    assert campaign_a.actors["pc_001"].position == campaign_b.actors["pc_001"].position
    assert areas_a == areas_b
    assert entities_a == entities_b


def test_guarded_bootstrap_branch_only_activates_for_supported_scenario_metadata(
    tmp_path: Path,
) -> None:
    repo = FileRepo(tmp_path / "storage")
    _save_non_supported_metadata_world(
        repo,
        world_id="world_not_supported",
        generator_id="playable_scenario_v0",
        params={
            "mode": "playable_scenario",
            "template_id": "unsupported_template",
            "area_count": 6,
            "layout_type": "branch",
            "difficulty": "easy",
        },
    )
    service = TurnService(repo)

    campaign_id = service.create_campaign(
        world_id="world_not_supported",
        map_id="map_generated",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )
    campaign = repo.get_campaign(campaign_id)

    assert campaign.actors["pc_001"].position == "area_001"
    assert "npc_guide_01" in campaign.entities
    assert [stack.definition_id for stack in campaign.items.values()] == ["crate_01"]
    assert "area_target" not in campaign.map.areas
    assert campaign.goal.text == "Define the main objective"


def test_non_scenario_world_still_uses_existing_bootstrap_path_unchanged(
    tmp_path: Path,
) -> None:
    repo = FileRepo(tmp_path / "storage")
    _save_non_supported_metadata_world(
        repo,
        world_id="world_regular",
        generator_id="stub",
        params={"seed_source": "test"},
    )
    service = TurnService(repo)

    campaign_id = service.create_campaign(
        world_id="world_regular",
        map_id="map_generated",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )
    campaign = repo.get_campaign(campaign_id)

    assert campaign.actors["pc_001"].position == "area_001"
    assert sorted(campaign.entities.keys()) == ["door_01", "npc_guide_01"]
    assert [stack.definition_id for stack in campaign.items.values()] == ["crate_01"]
    assert sorted(campaign.map.areas.keys()) == ["area_001", "area_002"]
    assert campaign.goal.text == "Define the main objective"


def test_watchtower_bootstrap_path_remains_unchanged(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)

    campaign_id = service.create_campaign(
        world_id=TEST_WATCHTOWER_WORLD_ID,
        map_id="map_watchtower",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )
    campaign = repo.get_campaign(campaign_id)

    assert campaign.actors["pc_001"].position == "village_gate"
    assert sorted(campaign.map.areas.keys()) == [
        "forest_path",
        "old_hut",
        "village_gate",
        "village_square",
        "watchtower_entrance",
        "watchtower_inside",
    ]
    assert "npc_village_guard" in campaign.entities


def test_builtin_scenario_preset_bootstraps_playable_campaign(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)

    campaign_id = service.create_campaign(
        world_id=DEV_KEY_GATE_SCENARIO_WORLD_ID,
        map_id="map_generated",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )
    campaign = repo.get_campaign(campaign_id)

    assert campaign.selected.world_id == DEV_KEY_GATE_SCENARIO_WORLD_ID
    assert campaign.actors["pc_001"].position == "area_start"
    assert sorted(campaign.entities.keys()) == [
        "clue_source_001",
        "gate_001",
        "hint_source_001",
    ]
    assert sorted(campaign.map.areas.keys()) == [
        "area_clue",
        "area_gate",
        "area_start",
        "area_target",
    ]
    assert campaign.goal.text == "Find the required item and enter the target area."


def test_builtin_scenario_preset_is_playable_through_real_runtime_path(
    tmp_path: Path,
) -> None:
    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)
    service.llm = _ScenarioRuntimeLLM()

    campaign_id = service.create_campaign(
        world_id=DEV_KEY_GATE_SCENARIO_WORLD_ID,
        map_id="map_generated",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )

    talk = service.submit_turn(campaign_id, "TALK_HINT")
    assert talk["applied_actions"][0]["tool"] == "scene_action"

    service.submit_turn(campaign_id, "MOVE_TO_CLUE")
    search = service.submit_turn(campaign_id, "SEARCH_CLUE")
    assert search["state_summary"]["active_actor_inventory"] == {"required_item_001": 1}

    service.submit_turn(campaign_id, "MOVE_TO_GATE")
    entered = service.submit_turn(campaign_id, "ENTER_TARGET")
    assert entered["applied_actions"][0]["tool"] == "move"
    assert entered["state_summary"]["active_area_id"] == "area_target"

    campaign = repo.get_campaign(campaign_id)
    assert campaign.goal.status == "completed"
    assert campaign.lifecycle.ended is True
    assert campaign.lifecycle.reason == "goal_achieved"


def test_builtin_scenario_preset_produces_stable_runtime_bootstrap(
    tmp_path: Path,
) -> None:
    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)

    campaign_a = repo.get_campaign(
        service.create_campaign(
            world_id=DEV_KEY_GATE_SCENARIO_WORLD_ID,
            map_id="map_generated",
            party_character_ids=["pc_001"],
            active_actor_id="pc_001",
        )
    )
    campaign_b = repo.get_campaign(
        service.create_campaign(
            world_id=DEV_KEY_GATE_SCENARIO_WORLD_ID,
            map_id="map_generated",
            party_character_ids=["pc_001"],
            active_actor_id="pc_001",
        )
    )

    assert campaign_a.goal.text == campaign_b.goal.text
    assert campaign_a.actors["pc_001"].position == campaign_b.actors["pc_001"].position
    assert {
        area_id: list(area.reachable_area_ids)
        for area_id, area in sorted(campaign_a.map.areas.items())
    } == {
        area_id: list(area.reachable_area_ids)
        for area_id, area in sorted(campaign_b.map.areas.items())
    }
    assert {
        entity_id: {
            "kind": entity.kind,
            "loc": entity.loc.id,
            "verbs": list(entity.verbs),
            "state": dict(entity.state),
        }
        for entity_id, entity in sorted(campaign_a.entities.items())
    } == {
        entity_id: {
            "kind": entity.kind,
            "loc": entity.loc.id,
            "verbs": list(entity.verbs),
            "state": dict(entity.state),
        }
        for entity_id, entity in sorted(campaign_b.entities.items())
    }
