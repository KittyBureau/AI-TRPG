from __future__ import annotations

import pytest

from backend.app.tool_executor import execute_tool_calls
from backend.domain.models import (
    ActorState,
    Campaign,
    Goal,
    MapArea,
    MapData,
    Milestone,
    Selected,
    SettingsSnapshot,
    ToolCall,
)


def _make_campaign() -> Campaign:
    selected = Selected(
        world_id="world_001",
        map_id="map_001",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )
    return Campaign(
        id="camp_test",
        selected=selected,
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
                    name="Side Room",
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
                meta={},
            )
        },
    )


def test_move_succeeds_with_explicit_actor_id() -> None:
    campaign = _make_campaign()
    call = ToolCall(
        id="call_move_001",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": "area_002"},
    )
    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])
    assert tool_feedback is None
    assert len(applied_actions) == 1
    assert applied_actions[0].result == {
        "from_area_id": "area_001",
        "to_area_id": "area_002",
    }
    assert campaign.actors["pc_001"].position == "area_002"


def test_move_uses_active_actor_when_actor_id_omitted() -> None:
    campaign = _make_campaign()
    call = ToolCall(
        id="call_move_002",
        tool="move",
        args={"to_area_id": "area_002"},
    )
    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])
    assert tool_feedback is None
    assert len(applied_actions) == 1
    assert campaign.actors["pc_001"].position == "area_002"


@pytest.mark.parametrize(
    "args",
    [
        {"actor_id": "pc_001", "to_area_id": "area_002", "from_area_id": "area_001"},
        {"actor_id": "pc_001", "to_area_id": "area_001"},
        {"actor_id": "pc_001", "to_area_id": "area_999"},
    ],
)
def test_move_rejects_invalid_args_without_state_change(args: dict) -> None:
    campaign = _make_campaign()
    call = ToolCall(id="call_move_fail", tool="move", args=args)
    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])
    assert applied_actions == []
    assert tool_feedback is not None
    assert tool_feedback.failed_calls[0].reason == "invalid_args"
    assert campaign.actors["pc_001"].position == "area_001"


def test_move_rejected_for_non_alive_actor() -> None:
    campaign = _make_campaign()
    campaign.actors["pc_001"].character_state = "dead"
    call = ToolCall(
        id="call_move_dead",
        tool="move",
        args={"actor_id": "pc_001", "to_area_id": "area_002"},
    )
    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])
    assert applied_actions == []
    assert tool_feedback is not None
    assert tool_feedback.failed_calls[0].reason == "actor_state_restricted"
