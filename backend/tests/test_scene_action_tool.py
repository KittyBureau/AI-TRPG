from __future__ import annotations

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
    assert campaign.entities["apple_01"].loc.type == "actor"
    assert campaign.entities["apple_01"].loc.id == "pc_001"

    drop_actions, drop_feedback = execute_tool_calls(campaign, "pc_001", [drop])
    assert drop_feedback is None
    assert len(drop_actions) == 1
    assert drop_actions[0].result["ok"] is True
    assert campaign.entities["apple_01"].loc.type == "area"
    assert campaign.entities["apple_01"].loc.id == "area_001"


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
