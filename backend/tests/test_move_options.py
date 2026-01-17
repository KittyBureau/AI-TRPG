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


def _make_campaign(map_data: MapData) -> Campaign:
    selected = Selected(
        world_id="world_001",
        map_id="map_001",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )
    campaign = Campaign(
        id="camp_test",
        selected=selected,
        settings_snapshot=SettingsSnapshot(),
        goal=Goal(text="Goal", status="active"),
        milestone=Milestone(current="intro", last_advanced_turn=0),
        map=map_data,
        actors={
            "pc_001": ActorState(
                position="area_001",
                hp=10,
                character_state="alive",
                meta={},
            )
        },
    )
    return campaign


def test_move_options_1hop_returns_neighbors() -> None:
    map_data = MapData(
        areas={
            "area_001": MapArea(
                id="area_001",
                name="Root",
                reachable_area_ids=["area_002", "area_003"],
            ),
            "area_002": MapArea(
                id="area_002",
                name="Side Room",
                reachable_area_ids=[],
            ),
            "area_003": MapArea(
                id="area_003",
                name="Hall",
                reachable_area_ids=[],
            ),
        },
        connections=[],
    )
    campaign = _make_campaign(map_data)
    call = ToolCall(id="call_001", tool="move_options", args={})
    applied_actions, tool_feedback = execute_tool_calls(
        campaign, "pc_001", [call]
    )
    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["options"] == [
        {"to_area_id": "area_002", "name": "Side Room"},
        {"to_area_id": "area_003", "name": "Hall"},
    ]


def test_move_options_does_not_change_positions() -> None:
    map_data = MapData(
        areas={
            "area_001": MapArea(
                id="area_001",
                name="Root",
                reachable_area_ids=["area_002"],
            ),
            "area_002": MapArea(
                id="area_002",
                name="Side Room",
                reachable_area_ids=[],
            ),
        },
        connections=[],
    )
    campaign = _make_campaign(map_data)
    before_positions = {
        actor_id: actor.position for actor_id, actor in campaign.actors.items()
    }
    call = ToolCall(id="call_002", tool="move_options", args={})
    applied_actions, tool_feedback = execute_tool_calls(
        campaign, "pc_001", [call]
    )
    assert tool_feedback is None
    assert len(applied_actions) == 1
    after_positions = {
        actor_id: actor.position for actor_id, actor in campaign.actors.items()
    }
    assert after_positions == before_positions


@pytest.mark.parametrize(
    "call_args,allowlist,state,expected_reason",
    [
        ({}, ["move"], "alive", "tool_not_allowed"),
        ({}, ["move_options"], "dead", "actor_state_restricted"),
    ],
)
def test_move_options_respects_allowlist_or_state(
    call_args: dict,
    allowlist: list,
    state: str,
    expected_reason: str,
) -> None:
    map_data = MapData(
        areas={
            "area_001": MapArea(
                id="area_001", name="Root", reachable_area_ids=["area_002"]
            ),
            "area_002": MapArea(
                id="area_002", name="Side Room", reachable_area_ids=[]
            ),
        },
        connections=[],
    )
    campaign = _make_campaign(map_data)
    campaign.allowlist = list(allowlist)
    campaign.actors["pc_001"].character_state = state
    call = ToolCall(id="call_fail", tool="move_options", args=call_args)
    applied_actions, tool_feedback = execute_tool_calls(
        campaign, "pc_001", [call]
    )
    assert applied_actions == []
    assert tool_feedback is not None
    assert tool_feedback.failed_calls[0].reason == expected_reason
