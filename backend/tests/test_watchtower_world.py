from __future__ import annotations

from pathlib import Path

from backend.app.tool_executor import execute_tool_calls
from backend.app.turn_service import TurnService
from backend.app.world_presets import (
    TEST_WATCHTOWER_TARGET_AREA_ID,
    TEST_WATCHTOWER_GATE_STACK_ID,
    TEST_WATCHTOWER_WORLD_ID,
)
from backend.domain.models import ToolCall
from backend.infra.file_repo import FileRepo


def test_create_campaign_bootstraps_static_watchtower_world(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)

    campaign_id = service.create_campaign(
        world_id=TEST_WATCHTOWER_WORLD_ID,
        map_id="map_watchtower",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )

    campaign = repo.get_campaign(campaign_id)

    assert campaign.selected.world_id == TEST_WATCHTOWER_WORLD_ID
    assert campaign.goal.text == "Find the tower key in the old hut and enter the watchtower."
    assert sorted(campaign.map.areas.keys()) == [
        "forest_path",
        "old_hut",
        "village_gate",
        "village_square",
        "watchtower_entrance",
        "watchtower_inside",
    ]
    assert campaign.actors["pc_001"].position == "village_gate"
    assert "npc_village_guard" in campaign.entities
    assert campaign.entities["npc_village_guard"].loc.id == "village_gate"
    assert campaign.entities["old_hut_clue"].kind == "container"
    assert "inventory_item_id" not in campaign.entities["old_hut_clue"].state
    assert "required_item_id" not in campaign.entities["watchtower_door"].state


def test_watchtower_gate_requires_key_and_completes_goal(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)
    campaign_id = service.create_campaign(
        world_id=TEST_WATCHTOWER_WORLD_ID,
        map_id="map_watchtower",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )
    campaign = repo.get_campaign(campaign_id)
    campaign.actors["pc_001"].position = "watchtower_entrance"

    blocked_call = ToolCall(
        id="call_blocked",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": TEST_WATCHTOWER_TARGET_AREA_ID},
    )
    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [blocked_call])

    assert applied_actions == []
    assert tool_feedback is not None
    assert tool_feedback.failed_calls[0].reason == "missing_required_item"
    assert campaign.actors["pc_001"].position == "watchtower_entrance"
    assert campaign.goal.status == "active"

    campaign.actors["pc_001"].position = "old_hut"
    search_call = ToolCall(
        id="call_search",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "search",
            "target_id": "old_hut_clue",
            "params": {},
        },
    )
    repeat_search_call = ToolCall(
        id="call_repeat_search",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "search",
            "target_id": "old_hut_clue",
            "params": {},
        },
    )
    applied_actions, tool_feedback = execute_tool_calls(
        campaign,
        "pc_001",
        [search_call, repeat_search_call],
    )

    assert tool_feedback is None
    assert [action.tool for action in applied_actions] == ["scene_action", "scene_action"]
    assert applied_actions[0].result["ok"] is True
    assert "tower key" in applied_actions[0].result["narrative"].lower()
    assert applied_actions[1].result["ok"] is True
    assert "nothing useful" in applied_actions[1].result["narrative"]
    assert campaign.actors["pc_001"].inventory == {}
    assert TEST_WATCHTOWER_GATE_STACK_ID in campaign.items
    revealed_stack = campaign.items[TEST_WATCHTOWER_GATE_STACK_ID]
    assert revealed_stack.definition_id == "tower_key"
    assert revealed_stack.parent_type == "area"
    assert revealed_stack.parent_id == "old_hut"

    take_call = ToolCall(
        id="call_take_key",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "take",
            "target_id": TEST_WATCHTOWER_GATE_STACK_ID,
            "params": {},
        },
    )
    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [take_call])

    assert tool_feedback is None
    assert [action.tool for action in applied_actions] == ["scene_action"]
    assert applied_actions[0].result["ok"] is True
    assert applied_actions[0].result["narrative"] == "You take Tower Key."
    moved_stack = campaign.items[TEST_WATCHTOWER_GATE_STACK_ID]
    assert moved_stack.parent_type == "actor"
    assert moved_stack.parent_id == "pc_001"
    assert campaign.actors["pc_001"].inventory == {"tower_key": 1}

    campaign.actors["pc_001"].position = "watchtower_entrance"
    move_call = ToolCall(
        id="call_move",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": TEST_WATCHTOWER_TARGET_AREA_ID},
    )
    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [move_call])

    assert tool_feedback is None
    assert [action.tool for action in applied_actions] == ["move"]
    assert campaign.actors["pc_001"].position == TEST_WATCHTOWER_TARGET_AREA_ID
    assert campaign.goal.status == "completed"


def test_watchtower_guard_talk_surfaces_hint(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)
    campaign_id = service.create_campaign(
        world_id=TEST_WATCHTOWER_WORLD_ID,
        map_id="map_watchtower",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )
    campaign = repo.get_campaign(campaign_id)

    talk_call = ToolCall(
        id="call_talk",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "talk",
            "target_id": "npc_village_guard",
            "params": {},
        },
    )
    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [talk_call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    assert applied_actions[0].result["ok"] is True
    assert "old hut" in applied_actions[0].result["narrative"].lower()
