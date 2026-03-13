from __future__ import annotations

import backend.app.tool_executor as tool_executor_module

from backend.app.item_runtime import create_runtime_item_stack
from backend.app.tool_executor import execute_tool_calls
from backend.domain.models import (
    ActorState,
    Campaign,
    Entity,
    EntityLocation,
    Goal,
    MapArea,
    MapData,
    Milestone,
    Selected,
    SettingsSnapshot,
    ToolCall,
)


def _base_campaign() -> Campaign:
    return Campaign(
        id="camp_scene",
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001", "pc_002"],
            active_actor_id="pc_001",
        ),
        settings_snapshot=SettingsSnapshot(),
        goal=Goal(text="Goal", status="active"),
        milestone=Milestone(current="intro", last_advanced_turn=0),
        map=MapData(
            areas={
                "area_001": MapArea(
                    id="area_001",
                    name="Start",
                    reachable_area_ids=["area_002"],
                ),
                "area_002": MapArea(
                    id="area_002",
                    name="Side",
                    reachable_area_ids=[],
                ),
            },
            connections=[],
        ),
        actors={
            "pc_001": ActorState(
                position="area_001",
                hp=10,
                character_state="alive",
                inventory={},
                meta={},
            ),
            "pc_002": ActorState(
                position="area_001",
                hp=10,
                character_state="alive",
                inventory={},
                meta={},
            ),
        },
        entities={},
    )


def test_scene_action_rejects_not_reachable() -> None:
    campaign = _base_campaign()
    campaign.entities["door_far"] = Entity(
        id="door_far",
        kind="object",
        label="Far Door",
        tags=["door"],
        loc=EntityLocation(type="area", id="area_002"),
        verbs=["inspect", "open"],
        state={"locked": False},
        props={"mass": 20},
    )
    call = ToolCall(
        id="call_not_reachable",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "inspect",
            "target_id": "door_far",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "not_reachable"


def test_scene_action_rejects_verb_not_allowed() -> None:
    campaign = _base_campaign()
    campaign.entities["door_01"] = Entity(
        id="door_01",
        kind="object",
        label="Rusty Door",
        tags=["door"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "open"],
        state={"locked": False},
        props={"mass": 20},
    )
    call = ToolCall(
        id="call_not_allowed",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "take",
            "target_id": "door_01",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "not_allowed"


def test_scene_action_open_locked_door_fails() -> None:
    campaign = _base_campaign()
    campaign.entities["door_locked"] = Entity(
        id="door_locked",
        kind="object",
        label="Locked Door",
        tags=["door"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "open"],
        state={"locked": True, "opened": False},
        props={"mass": 30},
    )
    call = ToolCall(
        id="call_locked_open",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "open",
            "target_id": "door_locked",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "locked"
    assert campaign.entities["door_locked"].state["opened"] is False


def test_scene_action_detach_respects_carry_limit() -> None:
    campaign = _base_campaign()
    campaign.actors["pc_001"].meta["carry_mass_limit"] = 10
    campaign.entities["bag_01"] = Entity(
        id="bag_01",
        kind="item",
        label="Small Bag",
        tags=["bag"],
        loc=EntityLocation(type="actor", id="pc_001"),
        verbs=["inspect", "drop"],
        state={},
        props={"mass": 8},
    )
    campaign.entities["door_01"] = Entity(
        id="door_01",
        kind="object",
        label="Detached Door",
        tags=["door"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "detach"],
        state={"locked": False},
        props={"mass": 5},
    )
    call = ToolCall(
        id="call_detach_limit",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "detach",
            "target_id": "door_01",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "carry_limit"
    assert campaign.entities["door_01"].loc.type == "area"


def test_scene_action_take_and_drop_updates_location() -> None:
    campaign = _base_campaign()
    campaign.actors["pc_001"].inventory = {"torch": 1}
    campaign.entities["apple_01"] = Entity(
        id="apple_01",
        kind="item",
        label="Apple",
        tags=["food"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "take"],
        state={},
        props={"mass": 1},
    )
    take = ToolCall(
        id="call_take",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "take",
            "target_id": "apple_01",
            "params": {},
        },
    )
    drop = ToolCall(
        id="call_drop",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "drop",
            "target_id": "apple_01",
            "params": {},
        },
    )

    take_actions, take_feedback = execute_tool_calls(campaign, "pc_001", [take])
    assert take_feedback is None
    assert len(take_actions) == 1
    assert take_actions[0].result["ok"] is True
    assert campaign.actors["pc_001"].inventory == {"torch": 1}
    assert campaign.entities["apple_01"].loc.type == "actor"
    assert campaign.entities["apple_01"].loc.id == "pc_001"

    drop_actions, drop_feedback = execute_tool_calls(campaign, "pc_001", [drop])
    assert drop_feedback is None
    assert len(drop_actions) == 1
    assert drop_actions[0].result["ok"] is True
    assert campaign.actors["pc_001"].inventory == {"torch": 1}
    assert campaign.entities["apple_01"].loc.type == "area"
    assert campaign.entities["apple_01"].loc.id == "area_001"
    assert campaign.actors["pc_001"].position == "area_001"


def test_scene_action_take_visible_area_stack_transfers_parent_to_actor() -> None:
    campaign = _base_campaign()
    crate_stack = create_runtime_item_stack(
        definition_id="crate_01",
        quantity=1,
        parent_type="area",
        parent_id="area_001",
        label="Old Crate",
        tags=["container"],
        props={"mass": 8},
        stackable=False,
        is_container=True,
        stack_id_salt="test_scene_action_take_stack",
    )
    campaign.items = {crate_stack.stack_id: crate_stack}
    call = ToolCall(
        id="call_take_stack",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "take",
            "target_id": crate_stack.stack_id,
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    assert applied_actions[0].result["ok"] is True
    assert campaign.items[crate_stack.stack_id].parent_type == "actor"
    assert campaign.items[crate_stack.stack_id].parent_id == "pc_001"
    assert campaign.actors["pc_001"].inventory == {"crate_01": 1}


def test_scene_action_drop_actor_stack_transfers_parent_to_area() -> None:
    campaign = _base_campaign()
    ration_stack = create_runtime_item_stack(
        definition_id="field_ration",
        quantity=1,
        parent_type="actor",
        parent_id="pc_001",
        label="Field Ration",
        props={"mass": 2},
        stack_id_salt="test_scene_action_drop_stack",
    )
    campaign.items = {ration_stack.stack_id: ration_stack}
    call = ToolCall(
        id="call_drop_stack",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "drop",
            "target_id": ration_stack.stack_id,
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    assert applied_actions[0].result["ok"] is True
    assert campaign.items[ration_stack.stack_id].parent_type == "area"
    assert campaign.items[ration_stack.stack_id].parent_id == "area_001"
    assert campaign.actors["pc_001"].inventory == {}


def test_scene_action_open_stack_container_sets_opened_state() -> None:
    campaign = _base_campaign()
    crate_stack = create_runtime_item_stack(
        definition_id="crate_01",
        quantity=1,
        parent_type="area",
        parent_id="area_001",
        label="Old Crate",
        tags=["container"],
        stackable=False,
        is_container=True,
        state={"opened": False},
        stack_id_salt="test_scene_action_open_stack_container",
    )
    campaign.items = {crate_stack.stack_id: crate_stack}
    call = ToolCall(
        id="call_open_stack_container",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "open",
            "target_id": crate_stack.stack_id,
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is True
    assert result["narrative"] == "You open Old Crate."
    assert campaign.items[crate_stack.stack_id].state["opened"] is True


def test_scene_action_search_closed_stack_container_requires_open() -> None:
    campaign = _base_campaign()
    crate_stack = create_runtime_item_stack(
        definition_id="crate_01",
        quantity=1,
        parent_type="area",
        parent_id="area_001",
        label="Old Crate",
        tags=["container"],
        stackable=False,
        is_container=True,
        state={"opened": False},
        stack_id_salt="test_scene_action_search_closed_stack_container:crate",
    )
    child_stack = create_runtime_item_stack(
        definition_id="coin",
        quantity=1,
        parent_type="item",
        parent_id=crate_stack.stack_id,
        label="Coin",
        stack_id_salt="test_scene_action_search_closed_stack_container:coin",
    )
    campaign.items = {
        crate_stack.stack_id: crate_stack,
        child_stack.stack_id: child_stack,
    }
    call = ToolCall(
        id="call_search_closed_stack_container",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "search",
            "target_id": crate_stack.stack_id,
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "not_allowed"
    assert "open Old Crate first" in result["narrative"]
    assert campaign.items[crate_stack.stack_id].state["opened"] is False


def test_scene_action_search_opened_stack_container_finds_child() -> None:
    campaign = _base_campaign()
    crate_stack = create_runtime_item_stack(
        definition_id="crate_01",
        quantity=1,
        parent_type="area",
        parent_id="area_001",
        label="Old Crate",
        tags=["container"],
        stackable=False,
        is_container=True,
        state={"opened": True},
        stack_id_salt="test_scene_action_search_opened_stack_container:crate",
    )
    child_stack = create_runtime_item_stack(
        definition_id="coin",
        quantity=1,
        parent_type="item",
        parent_id=crate_stack.stack_id,
        label="Coin",
        stack_id_salt="test_scene_action_search_opened_stack_container:coin",
    )
    campaign.items = {
        crate_stack.stack_id: crate_stack,
        child_stack.stack_id: child_stack,
    }
    call = ToolCall(
        id="call_search_opened_stack_container",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "search",
            "target_id": crate_stack.stack_id,
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is True
    assert result["narrative"] == "You search Old Crate and find Coin."
    assert campaign.items[child_stack.stack_id].parent_type == "item"
    assert campaign.items[child_stack.stack_id].parent_id == crate_stack.stack_id


def test_scene_action_search_fixed_entity_grant_source_still_works() -> None:
    campaign = _base_campaign()
    campaign.entities["old_hut_clue"] = Entity(
        id="old_hut_clue",
        kind="object",
        label="Dusty Table",
        tags=["clue"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "search"],
        state={"inventory_item_id": "tower_key", "inventory_quantity": 1},
        props={},
    )
    call = ToolCall(
        id="call_search_entity_grant_source",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "search",
            "target_id": "old_hut_clue",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is True
    assert "tower_key" in result["narrative"]
    assert campaign.actors["pc_001"].inventory == {"tower_key": 1}


def test_scene_action_area_search_prefers_entity_grant_source_before_stack_discovery() -> None:
    campaign = _base_campaign()
    campaign.entities["old_hut_clue"] = Entity(
        id="old_hut_clue",
        kind="object",
        label="Dusty Table",
        tags=["clue"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "search"],
        state={"inventory_item_id": "tower_key", "inventory_quantity": 1},
        props={},
    )
    crate_stack = create_runtime_item_stack(
        definition_id="crate_01",
        quantity=1,
        parent_type="area",
        parent_id="area_001",
        label="Old Crate",
        tags=["container"],
        stackable=False,
        is_container=True,
        state={"opened": True},
        stack_id_salt="test_scene_action_area_search_prefers_entity:crate",
    )
    child_stack = create_runtime_item_stack(
        definition_id="coin",
        quantity=1,
        parent_type="item",
        parent_id=crate_stack.stack_id,
        label="Coin",
        stack_id_salt="test_scene_action_area_search_prefers_entity:coin",
    )
    campaign.items = {
        crate_stack.stack_id: crate_stack,
        child_stack.stack_id: child_stack,
    }
    call = ToolCall(
        id="call_area_search_entity_before_stack",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "search",
            "target_id": "area_001",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is True
    assert result["narrative"] == "You search the area and find tower_key in Dusty Table."
    assert campaign.actors["pc_001"].inventory == {"tower_key": 1}


def test_scene_action_area_search_falls_back_to_visible_stack_discovery() -> None:
    campaign = _base_campaign()
    crate_stack = create_runtime_item_stack(
        definition_id="crate_01",
        quantity=1,
        parent_type="area",
        parent_id="area_001",
        label="Old Crate",
        tags=["container"],
        stackable=False,
        is_container=True,
        state={"opened": True},
        stack_id_salt="test_scene_action_area_search_stack_fallback:crate",
    )
    child_stack = create_runtime_item_stack(
        definition_id="coin",
        quantity=1,
        parent_type="item",
        parent_id=crate_stack.stack_id,
        label="Coin",
        stack_id_salt="test_scene_action_area_search_stack_fallback:coin",
    )
    campaign.items = {
        crate_stack.stack_id: crate_stack,
        child_stack.stack_id: child_stack,
    }
    call = ToolCall(
        id="call_area_search_stack_fallback",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "search",
            "target_id": "area_001",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is True
    assert result["narrative"] == "You search the area and find Coin in Old Crate."
    assert campaign.actors["pc_001"].inventory == {}


def test_scene_action_stack_take_uses_hybrid_carry_mass_counting() -> None:
    campaign = _base_campaign()
    campaign.actors["pc_001"].meta["carry_mass_limit"] = 10
    campaign.entities["bag_01"] = Entity(
        id="bag_01",
        kind="item",
        label="Bag",
        tags=["bag"],
        loc=EntityLocation(type="actor", id="pc_001"),
        verbs=["inspect", "drop"],
        state={},
        props={"mass": 5},
    )
    carried_stack = create_runtime_item_stack(
        definition_id="toolkit",
        quantity=1,
        parent_type="actor",
        parent_id="pc_001",
        label="Toolkit",
        props={"mass": 4},
        stackable=False,
        stack_id_salt="test_scene_action_hybrid_mass:carried",
    )
    target_stack = create_runtime_item_stack(
        definition_id="anvil",
        quantity=1,
        parent_type="area",
        parent_id="area_001",
        label="Anvil",
        props={"mass": 2},
        stackable=False,
        stack_id_salt="test_scene_action_hybrid_mass:target",
    )
    campaign.items = {
        carried_stack.stack_id: carried_stack,
        target_stack.stack_id: target_stack,
    }
    call = ToolCall(
        id="call_take_stack_limit",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "take",
            "target_id": target_stack.stack_id,
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "carry_limit"
    assert campaign.items[target_stack.stack_id].parent_type == "area"
    assert campaign.items[target_stack.stack_id].parent_id == "area_001"
    assert campaign.actors["pc_001"].inventory == {"toolkit": 1}


def test_scene_action_exception_rolls_back_entity_changes(
    monkeypatch,
) -> None:
    campaign = _base_campaign()
    campaign.entities["apple_01"] = Entity(
        id="apple_01",
        kind="item",
        label="Apple",
        tags=["food"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "take"],
        state={},
        props={"mass": 1},
    )
    before = campaign.model_dump(mode="python")

    def _boom(*args, **kwargs) -> None:
        raise RuntimeError("patch failed")

    monkeypatch.setattr(tool_executor_module, "_append_entity_patch", _boom)
    call = ToolCall(
        id="call_take_boom",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "take",
            "target_id": "apple_01",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "scene_action_failed"
    assert campaign.model_dump(mode="python") == before


def test_scene_action_exception_rolls_back_item_changes(
    monkeypatch,
) -> None:
    campaign = _base_campaign()
    crate_stack = create_runtime_item_stack(
        definition_id="crate_01",
        quantity=1,
        parent_type="area",
        parent_id="area_001",
        label="Old Crate",
        props={"mass": 8},
        stackable=False,
        is_container=True,
        stack_id_salt="test_scene_action_stack_rollback",
    )
    campaign.items = {crate_stack.stack_id: crate_stack}
    before = campaign.model_dump(mode="python")
    real_transfer = tool_executor_module.transfer_stack_parent

    def _boom(*args, **kwargs):
        real_transfer(*args, **kwargs)
        raise RuntimeError("transfer failed")

    monkeypatch.setattr(tool_executor_module, "transfer_stack_parent", _boom)
    call = ToolCall(
        id="call_take_stack_boom",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "take",
            "target_id": crate_stack.stack_id,
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "scene_action_failed"
    assert campaign.model_dump(mode="python") == before


def test_scene_action_actor_context_mismatch_rejected() -> None:
    campaign = _base_campaign()
    campaign.entities["door_01"] = Entity(
        id="door_01",
        kind="object",
        label="Rusty Door",
        tags=["door"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect"],
        state={},
        props={"mass": 20},
    )
    call = ToolCall(
        id="call_mismatch",
        tool="scene_action",
        args={
            "actor_id": "pc_002",
            "action": "inspect",
            "target_id": "door_01",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert applied_actions == []
    assert tool_feedback is not None
    assert tool_feedback.failed_calls[0].reason == "actor_context_mismatch"
