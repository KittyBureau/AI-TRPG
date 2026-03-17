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
    assert campaign.items == {}


def test_scene_action_detach_creates_actor_stack_and_removes_entity() -> None:
    campaign = _base_campaign()
    campaign.entities["door_01"] = Entity(
        id="door_01",
        kind="object",
        label="Detached Door",
        tags=["door", "metal"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "detach"],
        state={"locked": False},
        props={"mass": 5},
    )
    call = ToolCall(
        id="call_detach_success",
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
    assert result["ok"] is True
    assert result["patches"]["entity_patches"] == []
    assert result["patches"]["new_entities"] == []
    assert result["patches"]["removed_entities"] == [
        {
            "id": "door_01",
            "kind": "object",
            "label": "Detached Door",
            "tags": ["door", "metal"],
            "loc": {"type": "area", "id": "area_001"},
            "verbs": ["inspect", "detach"],
            "state": {"locked": False},
            "props": {"mass": 5},
        }
    ]
    assert "door_01" not in campaign.entities
    assert campaign.actors["pc_001"].inventory == {"door_01": 1}
    assert sorted(campaign.items.keys())
    only_stack = next(iter(campaign.items.values()))
    assert only_stack.definition_id == "door_01"
    assert only_stack.quantity == 1
    assert only_stack.parent_type == "actor"
    assert only_stack.parent_id == "pc_001"
    assert only_stack.label == "Detached Door"
    assert only_stack.tags == ["door", "metal"]
    assert only_stack.state == {"locked": False, "detached": True}
    assert only_stack.props == {"mass": 5}
    assert only_stack.stackable is False
    assert only_stack.is_container is False


def test_scene_action_detach_rejects_container_entities() -> None:
    campaign = _base_campaign()
    campaign.entities["crate_01"] = Entity(
        id="crate_01",
        kind="container",
        label="Supply Crate",
        tags=["crate"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "detach"],
        state={},
        props={"mass": 8},
    )
    call = ToolCall(
        id="call_detach_container",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "detach",
            "target_id": "crate_01",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "not_allowed"
    assert campaign.entities["crate_01"].kind == "container"
    assert campaign.items == {}


def test_scene_action_detach_rejects_entities_with_children() -> None:
    campaign = _base_campaign()
    campaign.entities["door_01"] = Entity(
        id="door_01",
        kind="object",
        label="Wall Panel",
        tags=["panel"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "detach"],
        state={},
        props={"mass": 4},
    )
    campaign.entities["bolt_01"] = Entity(
        id="bolt_01",
        kind="item",
        label="Hidden Bolt",
        tags=["metal"],
        loc=EntityLocation(type="entity", id="door_01"),
        verbs=["inspect", "take"],
        state={},
        props={"mass": 1},
    )
    call = ToolCall(
        id="call_detach_children",
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
    assert result["error"]["code"] == "not_allowed"
    assert "door_01" in campaign.entities
    assert "bolt_01" in campaign.entities
    assert campaign.items == {}


def test_scene_action_detach_rejects_entity_without_detach_verb() -> None:
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
        id="call_detach_not_allowed",
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
    assert result["error"]["code"] == "not_allowed"
    assert "door_01" in campaign.entities
    assert campaign.items == {}


def test_scene_action_take_legacy_portable_entity_creates_actor_stack() -> None:
    campaign = _base_campaign()
    torch_stack = create_runtime_item_stack(
        definition_id="torch",
        quantity=1,
        parent_type="actor",
        parent_id="pc_001",
        label="torch",
        stack_id_salt="test_scene_take_drop:pc_001:torch",
    )
    campaign.items = {torch_stack.stack_id: torch_stack}
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
    call = ToolCall(
        id="call_take",
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
    assert result["ok"] is True
    assert result["patches"]["entity_patches"] == []
    assert result["patches"]["new_entities"] == []
    assert result["patches"]["removed_entities"] == [
        {
            "id": "apple_01",
            "kind": "item",
            "label": "Apple",
            "tags": ["food"],
            "loc": {"type": "area", "id": "area_001"},
            "verbs": ["inspect", "take"],
            "state": {},
            "props": {"mass": 1},
        }
    ]
    assert "apple_01" not in campaign.entities
    assert campaign.actors["pc_001"].inventory == {"apple_01": 1, "torch": 1}
    assert len(campaign.items) == 2
    apple_stack = next(
        stack for stack in campaign.items.values() if stack.definition_id == "apple_01"
    )
    assert apple_stack.quantity == 1
    assert apple_stack.parent_type == "actor"
    assert apple_stack.parent_id == "pc_001"
    assert apple_stack.label == "Apple"
    assert apple_stack.tags == ["food"]
    assert apple_stack.state == {}
    assert apple_stack.props == {"mass": 1}
    assert apple_stack.stackable is False
    assert apple_stack.is_container is False


def test_scene_action_take_legacy_portable_entity_respects_carry_limit() -> None:
    campaign = _base_campaign()
    campaign.actors["pc_001"].meta["carry_mass_limit"] = 1
    campaign.entities["anvil_01"] = Entity(
        id="anvil_01",
        kind="item",
        label="Anvil",
        tags=["metal"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "take"],
        state={},
        props={"mass": 2},
    )
    call = ToolCall(
        id="call_take_limit",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "take",
            "target_id": "anvil_01",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "carry_limit"
    assert "anvil_01" in campaign.entities
    assert campaign.entities["anvil_01"].loc.type == "area"
    assert campaign.items == {}
    assert campaign.actors["pc_001"].inventory == {}


def test_scene_action_take_rejects_container_entity_conversion() -> None:
    campaign = _base_campaign()
    campaign.entities["crate_01"] = Entity(
        id="crate_01",
        kind="container",
        label="Supply Crate",
        tags=["crate"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "take"],
        state={},
        props={"mass": 8},
    )
    call = ToolCall(
        id="call_take_container",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "take",
            "target_id": "crate_01",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "not_allowed"
    assert result["error"]["message"] == "take target is container: crate_01"
    assert "crate_01" in campaign.entities
    assert campaign.items == {}


def test_scene_action_take_rejects_npc_entity_conversion() -> None:
    campaign = _base_campaign()
    campaign.entities["npc_01"] = Entity(
        id="npc_01",
        kind="npc",
        label="Wary Guard",
        tags=["guard"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "take", "talk"],
        state={},
        props={"mass": 20},
    )
    call = ToolCall(
        id="call_take_npc",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "take",
            "target_id": "npc_01",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "not_allowed"
    assert result["error"]["message"] == "take target is npc: npc_01"
    assert "npc_01" in campaign.entities
    assert campaign.items == {}


def test_scene_action_take_rejects_entities_with_children_for_conversion() -> None:
    campaign = _base_campaign()
    campaign.entities["bag_01"] = Entity(
        id="bag_01",
        kind="item",
        label="Field Bag",
        tags=["bag"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "take"],
        state={},
        props={"mass": 2},
    )
    campaign.entities["note_01"] = Entity(
        id="note_01",
        kind="item",
        label="Folded Note",
        tags=["note"],
        loc=EntityLocation(type="entity", id="bag_01"),
        verbs=["inspect", "take"],
        state={},
        props={"mass": 1},
    )
    call = ToolCall(
        id="call_take_with_children",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "take",
            "target_id": "bag_01",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "not_allowed"
    assert result["error"]["message"] == "take target has child entities: bag_01"
    assert "bag_01" in campaign.entities
    assert "note_01" in campaign.entities
    assert campaign.items == {}


def test_scene_action_take_rejects_entity_inventory_sources_for_conversion() -> None:
    campaign = _base_campaign()
    campaign.entities["stash_01"] = Entity(
        id="stash_01",
        kind="object",
        label="Loose Floorboard",
        tags=["stash"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "search", "take"],
        state={"inventory_item_id": "tower_key", "inventory_quantity": 1},
        props={"mass": 1},
    )
    call = ToolCall(
        id="call_take_inventory_source",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "take",
            "target_id": "stash_01",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "not_allowed"
    assert result["error"]["message"] == "take target is inventory source: stash_01"
    assert "stash_01" in campaign.entities
    assert campaign.items == {}


def test_scene_action_take_portable_child_entity_creates_actor_stack() -> None:
    campaign = _base_campaign()
    campaign.entities["crate_01"] = Entity(
        id="crate_01",
        kind="container",
        label="Supply Crate",
        tags=["crate"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "open", "search"],
        state={"opened": True},
        props={"mass": 8},
    )
    campaign.entities["bolt_01"] = Entity(
        id="bolt_01",
        kind="item",
        label="Loose Bolt",
        tags=["metal"],
        loc=EntityLocation(type="entity", id="crate_01"),
        verbs=["inspect", "take"],
        state={"worn": True},
        props={"mass": 1},
    )
    call = ToolCall(
        id="call_take_portable_child",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "take",
            "target_id": "bolt_01",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is True
    assert result["patches"]["removed_entities"] == [
        {
            "id": "bolt_01",
            "kind": "item",
            "label": "Loose Bolt",
            "tags": ["metal"],
            "loc": {"type": "entity", "id": "crate_01"},
            "verbs": ["inspect", "take"],
            "state": {"worn": True},
            "props": {"mass": 1},
        }
    ]
    assert "crate_01" in campaign.entities
    assert "bolt_01" not in campaign.entities
    assert campaign.actors["pc_001"].inventory == {"bolt_01": 1}
    bolt_stack = next(
        stack for stack in campaign.items.values() if stack.definition_id == "bolt_01"
    )
    assert bolt_stack.parent_type == "actor"
    assert bolt_stack.parent_id == "pc_001"
    assert bolt_stack.state == {"worn": True}
    assert bolt_stack.stackable is False


def test_scene_action_drop_legacy_actor_entity_creates_area_stack() -> None:
    campaign = _base_campaign()
    campaign.entities["apple_01"] = Entity(
        id="apple_01",
        kind="item",
        label="Apple",
        tags=["food"],
        loc=EntityLocation(type="actor", id="pc_001"),
        verbs=["inspect", "drop"],
        state={},
        props={"mass": 1},
    )
    call = ToolCall(
        id="call_drop_legacy_entity",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "drop",
            "target_id": "apple_01",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is True
    assert result["patches"]["entity_patches"] == []
    assert result["patches"]["new_entities"] == []
    assert result["patches"]["removed_entities"] == [
        {
            "id": "apple_01",
            "kind": "item",
            "label": "Apple",
            "tags": ["food"],
            "loc": {"type": "actor", "id": "pc_001"},
            "verbs": ["inspect", "drop"],
            "state": {},
            "props": {"mass": 1},
        }
    ]
    assert "apple_01" not in campaign.entities
    assert campaign.actors["pc_001"].inventory == {}
    assert len(campaign.items) == 1
    apple_stack = next(iter(campaign.items.values()))
    assert apple_stack.definition_id == "apple_01"
    assert apple_stack.parent_type == "area"
    assert apple_stack.parent_id == "area_001"
    assert apple_stack.label == "Apple"
    assert apple_stack.tags == ["food"]
    assert apple_stack.state == {}
    assert apple_stack.props == {"mass": 1}
    assert apple_stack.stackable is False


def test_scene_action_drop_rejects_container_entity_conversion() -> None:
    campaign = _base_campaign()
    campaign.entities["crate_01"] = Entity(
        id="crate_01",
        kind="container",
        label="Supply Crate",
        tags=["crate"],
        loc=EntityLocation(type="actor", id="pc_001"),
        verbs=["inspect", "drop"],
        state={},
        props={"mass": 8},
    )
    call = ToolCall(
        id="call_drop_container",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "drop",
            "target_id": "crate_01",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "not_allowed"
    assert result["error"]["message"] == "drop target is container: crate_01"
    assert "crate_01" in campaign.entities
    assert campaign.items == {}


def test_scene_action_drop_rejects_npc_entity_conversion() -> None:
    campaign = _base_campaign()
    campaign.entities["npc_01"] = Entity(
        id="npc_01",
        kind="npc",
        label="Wary Guard",
        tags=["guard"],
        loc=EntityLocation(type="actor", id="pc_001"),
        verbs=["inspect", "drop", "talk"],
        state={},
        props={"mass": 20},
    )
    call = ToolCall(
        id="call_drop_npc",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "drop",
            "target_id": "npc_01",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "not_allowed"
    assert result["error"]["message"] == "drop target is npc: npc_01"
    assert "npc_01" in campaign.entities
    assert campaign.items == {}


def test_scene_action_drop_rejects_entities_with_children_for_conversion() -> None:
    campaign = _base_campaign()
    campaign.entities["bag_01"] = Entity(
        id="bag_01",
        kind="item",
        label="Field Bag",
        tags=["bag"],
        loc=EntityLocation(type="actor", id="pc_001"),
        verbs=["inspect", "drop"],
        state={},
        props={"mass": 2},
    )
    campaign.entities["note_01"] = Entity(
        id="note_01",
        kind="item",
        label="Folded Note",
        tags=["note"],
        loc=EntityLocation(type="entity", id="bag_01"),
        verbs=["inspect", "take"],
        state={},
        props={"mass": 1},
    )
    call = ToolCall(
        id="call_drop_with_children",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "drop",
            "target_id": "bag_01",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "not_allowed"
    assert result["error"]["message"] == "drop target has child entities: bag_01"
    assert "bag_01" in campaign.entities
    assert "note_01" in campaign.entities
    assert campaign.items == {}


def test_scene_action_drop_rejects_entity_inventory_sources_for_conversion() -> None:
    campaign = _base_campaign()
    campaign.entities["stash_01"] = Entity(
        id="stash_01",
        kind="object",
        label="Loose Floorboard",
        tags=["stash"],
        loc=EntityLocation(type="actor", id="pc_001"),
        verbs=["inspect", "search", "drop"],
        state={"inventory_item_id": "tower_key", "inventory_quantity": 1},
        props={"mass": 1},
    )
    call = ToolCall(
        id="call_drop_inventory_source",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "drop",
            "target_id": "stash_01",
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "not_allowed"
    assert result["error"]["message"] == "drop target is inventory source: stash_01"
    assert "stash_01" in campaign.entities
    assert campaign.items == {}


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


def test_scene_action_use_explicit_stack_id_succeeds_for_actor_held_stack() -> None:
    campaign = _base_campaign()
    lever = Entity(
        id="lever_01",
        kind="object",
        label="Ancient Lever",
        tags=["mechanism"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "use"],
        state={"used": False},
        props={},
    )
    torch_stack = create_runtime_item_stack(
        definition_id="torch",
        quantity=2,
        parent_type="actor",
        parent_id="pc_001",
        label="Torch",
        state={"consume_on_use": True},
        stack_id_salt="test_scene_action_use_explicit_stack",
    )
    campaign.entities[lever.id] = lever
    campaign.items = {torch_stack.stack_id: torch_stack}
    call = ToolCall(
        id="call_use_explicit_stack",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "use",
            "target_id": lever.id,
            "params": {"item_id": torch_stack.stack_id},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is True
    assert result["narrative"] == "You use Torch on Ancient Lever."
    assert campaign.entities[lever.id].state["used"] is True
    assert campaign.items[torch_stack.stack_id].quantity == 1
    assert campaign.actors["pc_001"].inventory == {"torch": 1}


def test_scene_action_use_explicit_item_id_falls_back_to_actor_stack() -> None:
    campaign = _base_campaign()
    brazier = Entity(
        id="brazier_01",
        kind="object",
        label="Cold Brazier",
        tags=["fire"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "use"],
        state={"used": False},
        props={},
    )
    torch_stack = create_runtime_item_stack(
        definition_id="torch",
        quantity=1,
        parent_type="actor",
        parent_id="pc_001",
        label="Torch",
        stack_id_salt="test_scene_action_use_item_id_fallback",
    )
    campaign.entities[brazier.id] = brazier
    campaign.items = {torch_stack.stack_id: torch_stack}
    call = ToolCall(
        id="call_use_item_id_fallback",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "use",
            "target_id": brazier.id,
            "params": {"item_id": "torch"},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is True
    assert result["narrative"] == "You use Torch on Cold Brazier."
    assert campaign.entities[brazier.id].state["used"] is True
    assert campaign.items[torch_stack.stack_id].quantity == 1


def test_scene_action_use_falls_back_to_selected_stack_id() -> None:
    campaign = _base_campaign()
    shrine = Entity(
        id="shrine_01",
        kind="object",
        label="Hidden Shrine",
        tags=["altar"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "use"],
        state={"used": False},
        props={},
    )
    key_stack = create_runtime_item_stack(
        definition_id="rusty_key",
        quantity=1,
        parent_type="actor",
        parent_id="pc_001",
        label="Rusty Key",
        stack_id_salt="test_scene_action_use_selected_stack",
    )
    campaign.entities[shrine.id] = shrine
    campaign.items = {key_stack.stack_id: key_stack}
    call = ToolCall(
        id="call_use_selected_stack",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "use",
            "target_id": shrine.id,
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(
        campaign,
        "pc_001",
        [call],
        selected_stack_id=key_stack.stack_id,
    )

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is True
    assert result["narrative"] == "You use Rusty Key on Hidden Shrine."
    assert campaign.entities[shrine.id].state["used"] is True


def test_scene_action_use_falls_back_to_selected_item_id() -> None:
    campaign = _base_campaign()
    brazier = Entity(
        id="brazier_02",
        kind="object",
        label="Cold Brazier",
        tags=["fire"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "use"],
        state={"used": False},
        props={},
    )
    torch_stack = create_runtime_item_stack(
        definition_id="torch",
        quantity=1,
        parent_type="actor",
        parent_id="pc_001",
        label="Torch",
        stack_id_salt="test_scene_action_use_selected_item",
    )
    campaign.entities[brazier.id] = brazier
    campaign.items = {torch_stack.stack_id: torch_stack}
    call = ToolCall(
        id="call_use_selected_item",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "use",
            "target_id": brazier.id,
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(
        campaign,
        "pc_001",
        [call],
        selected_item_id="torch",
    )

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is True
    assert result["narrative"] == "You use Torch on Cold Brazier."
    assert campaign.entities[brazier.id].state["used"] is True


def test_scene_action_use_invalid_selected_stack_fails_cleanly() -> None:
    campaign = _base_campaign()
    shrine = Entity(
        id="shrine_01",
        kind="object",
        label="Hidden Shrine",
        tags=["altar"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "use"],
        state={"used": False},
        props={},
    )
    campaign.entities[shrine.id] = shrine
    call = ToolCall(
        id="call_use_missing_selected_stack",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "use",
            "target_id": shrine.id,
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(
        campaign,
        "pc_001",
        [call],
        selected_stack_id="stk_missing_item_001",
    )

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["narrative"] == "You have no valid selected item to use."
    assert result["error"]["code"] == "missing_item"
    assert result["error"]["message"] == "no valid active selected item"
    assert campaign.entities[shrine.id].state["used"] is False


def test_scene_action_use_stale_selected_stack_does_not_fallback_to_item_hint() -> None:
    campaign = _base_campaign()
    shrine = Entity(
        id="shrine_02",
        kind="object",
        label="Hidden Shrine",
        tags=["altar"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "use"],
        state={"used": False},
        props={},
    )
    torch_stack_a = create_runtime_item_stack(
        stack_id="stk_torch_0001aaaa",
        definition_id="torch",
        quantity=1,
        parent_type="actor",
        parent_id="pc_001",
        label="Torch",
        props={"variant": "old"},
    )
    torch_stack_b = create_runtime_item_stack(
        stack_id="stk_torch_ffff0002",
        definition_id="torch",
        quantity=1,
        parent_type="actor",
        parent_id="pc_001",
        label="Torch",
        props={"variant": "new"},
    )
    campaign.entities[shrine.id] = shrine
    campaign.items = {
        torch_stack_a.stack_id: torch_stack_a,
        torch_stack_b.stack_id: torch_stack_b,
    }
    call = ToolCall(
        id="call_use_stale_selected_stack",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "use",
            "target_id": shrine.id,
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(
        campaign,
        "pc_001",
        [call],
        selected_stack_id="stk_missing_item_001",
        selected_item_id="torch",
    )

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["narrative"] == "You have no valid selected item to use."
    assert result["error"]["code"] == "missing_item"
    assert result["error"]["message"] == "no valid active selected item"
    assert campaign.entities[shrine.id].state["used"] is False
    assert campaign.actors["pc_001"].inventory == {"torch": 2}


def test_scene_action_use_item_only_consumes_stack_and_deletes_zero_quantity() -> None:
    campaign = _base_campaign()
    tonic_stack = create_runtime_item_stack(
        definition_id="healing_tonic",
        quantity=1,
        parent_type="actor",
        parent_id="pc_001",
        label="Healing Tonic",
        state={"consume_on_use": True},
        stack_id_salt="test_scene_action_use_item_only",
    )
    campaign.items = {tonic_stack.stack_id: tonic_stack}
    call = ToolCall(
        id="call_use_item_only",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "use",
            "params": {"item_id": tonic_stack.stack_id},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is True
    assert result["narrative"] == "You use Healing Tonic."
    assert tonic_stack.stack_id not in campaign.items
    assert campaign.actors["pc_001"].inventory == {}


def test_scene_action_use_exception_rolls_back_item_and_entity_changes(
    monkeypatch,
) -> None:
    campaign = _base_campaign()
    shrine = Entity(
        id="shrine_01",
        kind="object",
        label="Hidden Shrine",
        tags=["altar"],
        loc=EntityLocation(type="area", id="area_001"),
        verbs=["inspect", "use"],
        state={"used": False},
        props={},
    )
    key_stack = create_runtime_item_stack(
        definition_id="rusty_key",
        quantity=1,
        parent_type="actor",
        parent_id="pc_001",
        label="Rusty Key",
        state={"consume_on_use": True},
        stack_id_salt="test_scene_action_use_rollback",
    )
    campaign.entities[shrine.id] = shrine
    campaign.items = {key_stack.stack_id: key_stack}
    tool_executor_module.normalize_campaign_items(campaign)
    before = campaign.model_dump(mode="python")

    def _boom(*args, **kwargs) -> None:
        raise RuntimeError("patch failed")

    monkeypatch.setattr(tool_executor_module, "_append_entity_patch", _boom)
    call = ToolCall(
        id="call_use_rollback",
        tool="scene_action",
        args={
            "actor_id": "pc_001",
            "action": "use",
            "target_id": shrine.id,
            "params": {},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(
        campaign,
        "pc_001",
        [call],
        selected_stack_id=key_stack.stack_id,
    )

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["ok"] is False
    assert result["error"]["code"] == "scene_action_failed"
    assert campaign.model_dump(mode="python") == before


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
        raise RuntimeError("grant failed")

    monkeypatch.setattr(tool_executor_module, "grant_item_to_actor", _boom)
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
