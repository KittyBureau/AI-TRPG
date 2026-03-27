from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any, Dict

import pytest

from backend.app.turn_service import TurnService
from backend.app.world_presets import (
    DEV_KEY_GATE_SCENARIO_WORLD_ID,
    TEST_WATCHTOWER_WORLD_ID,
)
from backend.domain.world_models import World, WorldGenerator, stable_world_timestamp
from backend.infra.file_repo import FileRepo

_SCENARIO_KEY_STACK_ID = "stk_clue_source_001_required_item_001"


class _ScenarioRuntimeLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        token = user_input.strip()
        if token.startswith("TALK:"):
            target_id = token.split(":", 1)[1].strip()
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": f"call_talk_{target_id}",
                        "tool": "scene_action",
                        "args": {
                            "actor_id": "pc_001",
                            "action": "talk",
                            "target_id": target_id,
                            "params": {},
                        },
                    }
                ],
            }
        if token.startswith("MOVE:"):
            to_area_id = token.split(":", 1)[1].strip()
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": f"call_move_{to_area_id}",
                        "tool": "move",
                        "args": {"actor_id": "pc_001", "to_area_id": to_area_id},
                    }
                ],
            }
        if token.startswith("SEARCH:"):
            target_id = token.split(":", 1)[1].strip()
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": f"call_search_{target_id}",
                        "tool": "scene_action",
                        "args": {
                            "actor_id": "pc_001",
                            "action": "search",
                            "target_id": target_id,
                            "params": {},
                        },
                    }
                ],
            }
        if token.startswith("TAKE:"):
            target_id = token.split(":", 1)[1].strip()
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": f"call_take_{target_id}",
                        "tool": "scene_action",
                        "args": {
                            "actor_id": "pc_001",
                            "action": "take",
                            "target_id": target_id,
                            "params": {},
                        },
                    }
                ],
            }
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
        if token == "TAKE_KEY":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_take_key",
                        "tool": "scene_action",
                        "args": {
                            "actor_id": "pc_001",
                            "action": "take",
                            "target_id": _SCENARIO_KEY_STACK_ID,
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


def _shortest_path_area_ids(
    service: TurnService,
    campaign_id: str,
    *,
    start_area_id: str,
    target_area_id: str,
) -> list[str]:
    campaign = service.repo.get_campaign(campaign_id)
    if start_area_id == target_area_id:
        return [start_area_id]
    queue = deque([[start_area_id]])
    visited = {start_area_id}
    while queue:
        path = queue.popleft()
        current = path[-1]
        for neighbor in sorted(campaign.map.areas[current].reachable_area_ids):
            if neighbor in visited:
                continue
            next_path = [*path, neighbor]
            if neighbor == target_area_id:
                return next_path
            visited.add(neighbor)
            queue.append(next_path)
    raise AssertionError(f"no path from {start_area_id} to {target_area_id}")


def _move_actor_to_area(
    service: TurnService,
    campaign_id: str,
    *,
    target_area_id: str,
) -> Dict[str, Any]:
    campaign = service.repo.get_campaign(campaign_id)
    start_area_id = campaign.actors["pc_001"].position
    assert isinstance(start_area_id, str) and start_area_id
    path = _shortest_path_area_ids(
        service,
        campaign_id,
        start_area_id=start_area_id,
        target_area_id=target_area_id,
    )
    response: Dict[str, Any] = {}
    for next_area_id in path[1:]:
        response = service.submit_turn(campaign_id, f"MOVE:{next_area_id}")
        assert response["applied_actions"][0]["tool"] == "move"
        assert response["state_summary"]["active_area_id"] == next_area_id
    return response


def _run_contract_playthrough(
    service: TurnService,
    campaign_id: str,
    *,
    visit_branch_first: bool = False,
) -> None:
    campaign = service.repo.get_campaign(campaign_id)
    fragment = campaign.scenario_runtime_fragment
    assert fragment is not None

    if visit_branch_first:
        branch_area_ids = [
            area_id
            for area_id in campaign.map.areas
            if "branch" in area_id
        ]
        assert branch_area_ids
        _move_actor_to_area(service, campaign_id, target_area_id=branch_area_ids[0])
        _move_actor_to_area(service, campaign_id, target_area_id=fragment.start_area_id)

    _move_actor_to_area(service, campaign_id, target_area_id=fragment.gate.from_area_id)
    blocked = service.submit_turn(campaign_id, f"MOVE:{fragment.gate.to_area_id}")
    assert blocked["applied_actions"] == []
    assert blocked["tool_feedback"]["failed_calls"][0]["reason"] == "missing_required_item"

    _move_actor_to_area(service, campaign_id, target_area_id=fragment.clue_area_id)
    search = service.submit_turn(
        campaign_id,
        f"SEARCH:{fragment.searchable_clue_source.interactable_id}",
    )
    assert search["applied_actions"][0]["tool"] == "scene_action"
    assert fragment.revealed_item.item_id in search["narrative_text"]

    take = service.submit_turn(
        campaign_id,
        f"TAKE:{_SCENARIO_KEY_STACK_ID}",
    )
    assert take["applied_actions"][0]["tool"] == "scene_action"
    assert take["state_summary"]["active_actor_inventory"] == {
        fragment.revealed_item.item_id: 1
    }

    _move_actor_to_area(service, campaign_id, target_area_id=fragment.gate.from_area_id)
    entered = service.submit_turn(campaign_id, f"MOVE:{fragment.gate.to_area_id}")
    assert entered["applied_actions"][0]["tool"] == "move"
    assert entered["state_summary"]["active_area_id"] == fragment.gate.to_area_id

    completed = service.repo.get_campaign(campaign_id)
    assert completed.goal.status == "completed"
    assert completed.lifecycle.ended is True
    assert completed.lifecycle.reason == "goal_achieved"


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
    assert campaign.scenario_runtime_fragment is not None
    assert campaign.scenario_runtime_fragment.gate.required_item_id == "required_item_001"
    assert campaign.scenario_runtime_fragment.completion.target_area_id == "area_target"
    assert campaign.entities["clue_source_001"].kind == "container"
    assert campaign.entities["clue_source_001"].state["search_loot_stack_id"] == _SCENARIO_KEY_STACK_ID
    assert campaign.entities["clue_source_001"].state["search_loot_definition_id"] == "required_item_001"
    assert "inventory_item_id" not in campaign.entities["clue_source_001"].state
    assert campaign.entities["gate_001"].state == {"locked": True}


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
    campaign = repo.get_campaign(campaign_id)
    assert campaign.scenario_runtime_fragment is not None
    repo.world_path("scenario_world_smoke").unlink()

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
    assert "required_item_001" in search["narrative_text"]
    assert search["state_summary"]["active_actor_inventory"] == {}
    assert search["state_summary"]["active_actor_inventory_stacks"] == []

    campaign = repo.get_campaign(campaign_id)
    assert campaign.items[_SCENARIO_KEY_STACK_ID].definition_id == "required_item_001"
    assert campaign.items[_SCENARIO_KEY_STACK_ID].parent_type == "area"
    assert campaign.items[_SCENARIO_KEY_STACK_ID].parent_id == "area_clue"

    take = service.submit_turn(campaign_id, "TAKE_KEY")
    assert take["applied_actions"][0]["tool"] == "scene_action"
    assert take["narrative_text"] == "You take required_item_001."
    assert take["state_summary"]["active_actor_inventory"] == {"required_item_001": 1}
    assert take["state_summary"]["active_actor_inventory_stacks"] == [
        {
            "stack_id": _SCENARIO_KEY_STACK_ID,
            "item_id": "required_item_001",
            "quantity": 1,
            "owner_actor_id": "pc_001",
            "location": {"type": "actor", "id": "pc_001"},
            "label": "required_item_001",
        }
    ]

    service.submit_turn(campaign_id, "MOVE_TO_GATE")
    entered = service.submit_turn(campaign_id, "ENTER_TARGET")
    assert entered["applied_actions"][0]["tool"] == "move"
    assert entered["state_summary"]["active_area_id"] == "area_target"

    campaign = repo.get_campaign(campaign_id)
    assert campaign.items[_SCENARIO_KEY_STACK_ID].parent_type == "actor"
    assert campaign.items[_SCENARIO_KEY_STACK_ID].parent_id == "pc_001"
    assert campaign.goal.status == "completed"
    assert campaign.lifecycle.ended is True
    assert campaign.lifecycle.reason == "goal_achieved"


@pytest.mark.parametrize(
    ("world_id", "area_count", "layout_type", "difficulty", "visit_branch_first"),
    [
        ("scenario_world_cover_linear_easy", 4, "linear", "easy", False),
        ("scenario_world_cover_gate_transit", 5, "linear", "easy", False),
        ("scenario_world_cover_clue_transit", 5, "linear", "standard", False),
        ("scenario_world_cover_branch", 5, "branch", "easy", True),
    ],
)
def test_scenario_runtime_contract_covers_multiple_topology_variants(
    tmp_path: Path,
    world_id: str,
    area_count: int,
    layout_type: str,
    difficulty: str,
    visit_branch_first: bool,
) -> None:
    repo = FileRepo(tmp_path / "storage")
    _save_scenario_world(
        repo,
        world_id=world_id,
        area_count=area_count,
        layout_type=layout_type,
        difficulty=difficulty,
    )
    service = TurnService(repo)
    service.llm = _ScenarioRuntimeLLM()

    campaign_id = service.create_campaign(
        world_id=world_id,
        map_id="map_generated",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )
    campaign = repo.get_campaign(campaign_id)
    assert campaign.scenario_runtime_fragment is not None
    assert campaign.scenario_runtime_fragment.gate.required_item_id == "required_item_001"
    assert campaign.scenario_runtime_fragment.completion.target_area_id == "area_target"

    repo.world_path(world_id).unlink()

    _run_contract_playthrough(
        service,
        campaign_id,
        visit_branch_first=visit_branch_first,
    )


def test_scenario_metadata_world_fails_explicitly_when_runtime_authority_is_missing(
    tmp_path: Path,
) -> None:
    repo = FileRepo(tmp_path / "storage")
    _save_scenario_world(
        repo,
        world_id="scenario_world_missing_fragment",
        area_count=4,
        layout_type="linear",
        difficulty="easy",
    )
    service = TurnService(repo)
    service.llm = _ScenarioRuntimeLLM()

    campaign_id = service.create_campaign(
        world_id="scenario_world_missing_fragment",
        map_id="map_generated",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )
    campaign = repo.get_campaign(campaign_id)
    campaign.scenario_runtime_fragment = None
    repo.save_campaign(campaign)

    failed = service.submit_turn(campaign_id, "MOVE_TO_CLUE")

    assert failed["applied_actions"] == []
    assert failed["tool_feedback"]["failed_calls"][0]["reason"] == "scenario_runtime_authority_missing"


def test_scenario_metadata_world_with_corrupted_runtime_fragment_fails_on_load(
    tmp_path: Path,
) -> None:
    repo = FileRepo(tmp_path / "storage")
    _save_scenario_world(
        repo,
        world_id="scenario_world_corrupted_fragment",
        area_count=4,
        layout_type="linear",
        difficulty="easy",
    )
    service = TurnService(repo)

    campaign_id = service.create_campaign(
        world_id="scenario_world_corrupted_fragment",
        map_id="map_generated",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )
    campaign_path = repo.campaigns_root / campaign_id / "campaign.json"
    payload = json.loads(campaign_path.read_text(encoding="utf-8"))
    del payload["scenario_runtime_fragment"]["gate"]["required_item_id"]
    campaign_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(Exception, match="required_item_id"):
        repo.get_campaign(campaign_id)


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


def test_scenario_metadata_world_requires_supported_runtime_bootstrap(
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

    with pytest.raises(
        ValueError,
        match="scenario runtime bootstrap unavailable for world: world_not_supported",
    ):
        service.create_campaign(
            world_id="world_not_supported",
            map_id="map_generated",
            party_character_ids=["pc_001"],
            active_actor_id="pc_001",
        )


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
    assert campaign.entities["clue_source_001"].kind == "container"
    assert campaign.entities["clue_source_001"].state["search_loot_stack_id"] == _SCENARIO_KEY_STACK_ID
    assert "inventory_item_id" not in campaign.entities["clue_source_001"].state
    assert campaign.entities["gate_001"].state == {"locked": True}


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
    assert "required_item_001" in search["narrative_text"]
    assert search["state_summary"]["active_actor_inventory"] == {}
    assert search["state_summary"]["active_actor_inventory_stacks"] == []

    campaign = repo.get_campaign(campaign_id)
    assert campaign.items[_SCENARIO_KEY_STACK_ID].parent_type == "area"
    assert campaign.items[_SCENARIO_KEY_STACK_ID].parent_id == "area_clue"

    take = service.submit_turn(campaign_id, "TAKE_KEY")
    assert take["narrative_text"] == "You take required_item_001."
    assert take["state_summary"]["active_actor_inventory"] == {"required_item_001": 1}

    service.submit_turn(campaign_id, "MOVE_TO_GATE")
    entered = service.submit_turn(campaign_id, "ENTER_TARGET")
    assert entered["applied_actions"][0]["tool"] == "move"
    assert entered["state_summary"]["active_area_id"] == "area_target"

    campaign = repo.get_campaign(campaign_id)
    assert campaign.items[_SCENARIO_KEY_STACK_ID].parent_type == "actor"
    assert campaign.items[_SCENARIO_KEY_STACK_ID].parent_id == "pc_001"
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
