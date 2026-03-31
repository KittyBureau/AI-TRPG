from __future__ import annotations

from backend.app.tool_executor import execute_tool_calls
from backend.app.turn_service import TurnService
from backend.app.world_presets import (
    MIDNIGHT_ARCHIVE_ARCHIVE_KEY_STACK_ID,
    MIDNIGHT_ARCHIVE_OFFICE_PASS_STACK_ID,
    MIDNIGHT_ARCHIVE_PAYOFF_ENTITY_ID,
    MIDNIGHT_ARCHIVE_ROUTING_SLIP_STACK_ID,
    MIDNIGHT_ARCHIVE_TARGET_AREA_ID,
    MIDNIGHT_ARCHIVE_WORLD_ID,
)
from backend.domain.models import ToolCall
from backend.infra.file_repo import FileRepo


def test_create_campaign_bootstraps_midnight_archive_world(tmp_path) -> None:
    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)

    campaign_id = service.create_campaign(
        world_id=MIDNIGHT_ARCHIVE_WORLD_ID,
        map_id="map_midnight_archive",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )

    campaign = repo.get_campaign(campaign_id)

    assert campaign.selected.world_id == MIDNIGHT_ARCHIVE_WORLD_ID
    assert (
        campaign.goal.text
        == "Reach the restricted archive and inspect the forged file shelf to recover proof that the inspection record was falsified."
    )
    assert sorted(campaign.map.areas.keys()) == [
        "clerk_office",
        "lobby",
        "reading_room",
        "restricted_archive",
        "returns_annex",
        "storage_room",
        "street_gate",
    ]
    assert campaign.actors["pc_001"].position == "street_gate"
    assert "porter_npc" in campaign.entities
    assert "assistant_archivist_npc" in campaign.entities
    assert "janitor_npc" in campaign.entities
    assert campaign.entities["returns_cart"].kind == "container"
    assert campaign.entities["desk_safe"].kind == "container"
    assert campaign.entities["janitor_npc"].props == {
        "combat_resolution": "npc_disabled",
        "combat_aftermath_hook": {
            "kind": "search_loot",
            "item_id": "routing_slip",
            "item_label": "Routing Slip",
        },
    }


def test_midnight_archive_official_route_requires_pass_then_key_then_final_interaction(
    tmp_path,
) -> None:
    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)
    campaign_id = service.create_campaign(
        world_id=MIDNIGHT_ARCHIVE_WORLD_ID,
        map_id="map_midnight_archive",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )
    campaign = repo.get_campaign(campaign_id)

    blocked_office_call = ToolCall(
        id="call_blocked_office",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": "clerk_office"},
    )
    campaign.actors["pc_001"].position = "lobby"
    applied_actions, tool_feedback = execute_tool_calls(
        campaign, "pc_001", [blocked_office_call]
    )

    assert applied_actions == []
    assert tool_feedback is not None
    assert tool_feedback.failed_calls[0].reason == "missing_required_item"

    search_pass = ToolCall(
        id="call_search_pass",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "search",
            "target_id": "lost_and_found_tray",
            "params": {},
        },
    )
    take_pass = ToolCall(
        id="call_take_pass",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "take",
            "target_id": MIDNIGHT_ARCHIVE_OFFICE_PASS_STACK_ID,
            "params": {},
        },
    )
    move_office = ToolCall(
        id="call_move_office",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": "clerk_office"},
    )
    open_safe = ToolCall(
        id="call_open_safe",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "open",
            "target_id": "desk_safe",
            "params": {},
        },
    )
    search_safe = ToolCall(
        id="call_search_safe",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "search",
            "target_id": "desk_safe",
            "params": {},
        },
    )
    take_key = ToolCall(
        id="call_take_key",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "take",
            "target_id": MIDNIGHT_ARCHIVE_ARCHIVE_KEY_STACK_ID,
            "params": {},
        },
    )
    move_storage = ToolCall(
        id="call_move_storage",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": "storage_room"},
    )
    move_archive = ToolCall(
        id="call_move_archive",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": MIDNIGHT_ARCHIVE_TARGET_AREA_ID},
    )
    inspect_shelf = ToolCall(
        id="call_inspect_shelf",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "inspect",
            "target_id": MIDNIGHT_ARCHIVE_PAYOFF_ENTITY_ID,
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(
        campaign,
        "pc_001",
        [
            search_pass,
            take_pass,
            move_office,
            open_safe,
            search_safe,
            take_key,
            move_storage,
            move_archive,
        ],
    )

    assert tool_feedback is None
    assert [action.tool for action in applied_actions] == [
        "scene_action",
        "scene_action",
        "move",
        "scene_action",
        "scene_action",
        "scene_action",
        "move",
        "move",
    ]
    assert campaign.items[MIDNIGHT_ARCHIVE_OFFICE_PASS_STACK_ID].parent_type == "actor"
    assert campaign.items[MIDNIGHT_ARCHIVE_ARCHIVE_KEY_STACK_ID].parent_type == "actor"
    assert campaign.actors["pc_001"].inventory == {
        "office_pass": 1,
        "archive_key": 1,
    }
    assert campaign.actors["pc_001"].position == MIDNIGHT_ARCHIVE_TARGET_AREA_ID
    assert campaign.goal.status == "active"

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [inspect_shelf])

    assert tool_feedback is None
    assert [action.tool for action in applied_actions] == ["scene_action"]
    assert applied_actions[0].result["ok"] is True
    assert "forged file shelf" in applied_actions[0].result["narrative"].lower()
    assert campaign.goal.status == "completed"


def test_midnight_archive_service_route_requires_routing_slip_and_final_interaction(
    tmp_path,
) -> None:
    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)
    campaign_id = service.create_campaign(
        world_id=MIDNIGHT_ARCHIVE_WORLD_ID,
        map_id="map_midnight_archive",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )
    campaign = repo.get_campaign(campaign_id)
    campaign.actors["pc_001"].position = "reading_room"

    search_routing = ToolCall(
        id="call_search_routing",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "search",
            "target_id": "returns_cart",
            "params": {},
        },
    )
    take_routing = ToolCall(
        id="call_take_routing",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "take",
            "target_id": MIDNIGHT_ARCHIVE_ROUTING_SLIP_STACK_ID,
            "params": {},
        },
    )
    move_annex = ToolCall(
        id="call_move_annex",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": "returns_annex"},
    )
    move_archive = ToolCall(
        id="call_move_archive",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": MIDNIGHT_ARCHIVE_TARGET_AREA_ID},
    )
    search_shelf = ToolCall(
        id="call_search_shelf",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "search",
            "target_id": MIDNIGHT_ARCHIVE_PAYOFF_ENTITY_ID,
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(
        campaign,
        "pc_001",
        [move_annex, move_archive],
    )

    assert [action.tool for action in applied_actions] == ["move"]
    assert tool_feedback is not None
    assert tool_feedback.failed_calls[0].reason == "missing_required_item"
    assert campaign.actors["pc_001"].position == "returns_annex"
    assert campaign.goal.status == "active"
    campaign.actors["pc_001"].position = "reading_room"

    applied_actions, tool_feedback = execute_tool_calls(
        campaign,
        "pc_001",
        [search_routing, take_routing, move_annex, move_archive],
    )

    assert tool_feedback is None
    assert [action.tool for action in applied_actions] == [
        "scene_action",
        "scene_action",
        "move",
        "move",
    ]
    assert campaign.items[MIDNIGHT_ARCHIVE_ROUTING_SLIP_STACK_ID].parent_type == "actor"
    assert campaign.actors["pc_001"].inventory == {"routing_slip": 1}
    assert "archive_key" not in campaign.actors["pc_001"].inventory
    assert campaign.actors["pc_001"].position == MIDNIGHT_ARCHIVE_TARGET_AREA_ID
    assert campaign.goal.status == "active"

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [search_shelf])

    assert tool_feedback is None
    assert [action.tool for action in applied_actions] == ["scene_action"]
    assert applied_actions[0].result["ok"] is True
    assert campaign.goal.status == "completed"


def test_midnight_archive_player_can_finish_without_entering_clerk_office(tmp_path) -> None:
    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)
    campaign_id = service.create_campaign(
        world_id=MIDNIGHT_ARCHIVE_WORLD_ID,
        map_id="map_midnight_archive",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )
    campaign = repo.get_campaign(campaign_id)

    move_lobby = ToolCall(
        id="call_move_lobby",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": "lobby"},
    )
    move_reading = ToolCall(
        id="call_move_reading",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": "reading_room"},
    )
    search_routing = ToolCall(
        id="call_search_routing",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "search",
            "target_id": "returns_cart",
            "params": {},
        },
    )
    take_routing = ToolCall(
        id="call_take_routing",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "take",
            "target_id": MIDNIGHT_ARCHIVE_ROUTING_SLIP_STACK_ID,
            "params": {},
        },
    )
    move_annex = ToolCall(
        id="call_move_annex",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": "returns_annex"},
    )
    move_archive = ToolCall(
        id="call_move_archive",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": MIDNIGHT_ARCHIVE_TARGET_AREA_ID},
    )
    inspect_shelf = ToolCall(
        id="call_inspect_shelf",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "inspect",
            "target_id": MIDNIGHT_ARCHIVE_PAYOFF_ENTITY_ID,
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(
        campaign,
        "pc_001",
        [
            move_lobby,
            move_reading,
            search_routing,
            take_routing,
            move_annex,
            move_archive,
            inspect_shelf,
        ],
    )

    assert tool_feedback is None
    assert campaign.actors["pc_001"].position == MIDNIGHT_ARCHIVE_TARGET_AREA_ID
    assert campaign.goal.status == "completed"
    assert campaign.actors["pc_001"].inventory == {"routing_slip": 1}
    assert "clerk_office" in campaign.map.areas
    assert "desk_safe" in campaign.entities
    assert all(action.result for action in applied_actions)


def test_midnight_archive_janitor_combat_aftermath_can_enable_service_route(tmp_path) -> None:
    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)
    campaign_id = service.create_campaign(
        world_id=MIDNIGHT_ARCHIVE_WORLD_ID,
        map_id="map_midnight_archive",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )
    campaign = repo.get_campaign(campaign_id)

    move_lobby = ToolCall(
        id="call_move_lobby",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": "lobby"},
    )
    move_reading = ToolCall(
        id="call_move_reading",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": "reading_room"},
    )
    move_annex = ToolCall(
        id="call_move_annex",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": "returns_annex"},
    )
    move_storage = ToolCall(
        id="call_move_storage",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": "storage_room"},
    )
    assault_janitor = ToolCall(
        id="call_assault_janitor",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "talk",
            "target_id": "janitor_npc",
            "params": {"approach": "violent"},
        },
    )
    search_janitor = ToolCall(
        id="call_search_janitor",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "search",
            "target_id": "janitor_npc",
            "params": {},
        },
    )
    move_back_annex = ToolCall(
        id="call_move_back_annex",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": "returns_annex"},
    )
    move_archive = ToolCall(
        id="call_move_archive",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": MIDNIGHT_ARCHIVE_TARGET_AREA_ID},
    )
    inspect_shelf = ToolCall(
        id="call_inspect_shelf",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "inspect",
            "target_id": MIDNIGHT_ARCHIVE_PAYOFF_ENTITY_ID,
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(
        campaign,
        "pc_001",
        [move_lobby, move_reading, move_annex, move_storage, assault_janitor],
    )

    assert tool_feedback is None
    assert [action.tool for action in applied_actions] == [
        "move",
        "move",
        "move",
        "move",
        "scene_action",
    ]
    assault_result = applied_actions[-1].result
    assert assault_result["ok"] is False
    assert assault_result["error"] == {
        "code": "combat_triggered",
        "message": "combat triggered: janitor_npc",
    }
    assert assault_result["hostility"]["triggered_outcomes"] == [
        {
            "outcome_id": "hostility_janitor_npc_combat_resolved",
            "type": "combat_resolved",
            "target_id": "janitor_npc",
            "scope_kind": "entity",
            "active": True,
            "resolution": "npc_disabled",
        }
    ]
    assert campaign.entities["janitor_npc"].state["disabled"] is True
    assert "search" in campaign.entities["janitor_npc"].verbs
    assert campaign.entities["returns_cart"].state.get("search_generated_loot") is not True

    applied_actions, tool_feedback = execute_tool_calls(
        campaign,
        "pc_001",
        [search_janitor],
    )

    assert tool_feedback is None
    assert [action.tool for action in applied_actions] == ["scene_action"]
    assert applied_actions[0].result["ok"] is True
    assert applied_actions[0].result["narrative"] == (
        "You search Night Janitor and find Routing Slip."
    )
    generated_routing_slip = next(
        stack
        for stack in campaign.items.values()
        if stack.definition_id == "routing_slip" and stack.parent_id == "storage_room"
    )

    take_routing = ToolCall(
        id="call_take_janitor_routing",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "take",
            "target_id": generated_routing_slip.stack_id,
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(
        campaign,
        "pc_001",
        [take_routing, move_back_annex, move_archive, inspect_shelf],
    )

    assert tool_feedback is None
    assert [action.tool for action in applied_actions] == [
        "scene_action",
        "move",
        "move",
        "scene_action",
    ]
    assert campaign.goal.status == "completed"
    assert campaign.actors["pc_001"].inventory == {"routing_slip": 1}
    assert campaign.actors["pc_001"].position == MIDNIGHT_ARCHIVE_TARGET_AREA_ID
    assert campaign.entities["returns_cart"].state.get("search_generated_loot") is not True
    assert campaign.entities["janitor_npc"].state["search_generated_loot"] is True
