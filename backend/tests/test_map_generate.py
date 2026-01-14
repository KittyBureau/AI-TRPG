from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.tool_executor import execute_tool_calls
from backend.domain.map_models import require_valid_map
from backend.domain.models import (
    Campaign,
    Goal,
    MapArea,
    MapData,
    Milestone,
    Selected,
    SettingsSnapshot,
    ToolCall,
)
from backend.domain.state_utils import ensure_positions_child, sync_state_positions
from backend.infra.file_repo import FileRepo


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
        positions={"pc_001": "area_001"},
        hp={"pc_001": 10},
        character_states={"pc_001": "alive"},
    )
    sync_state_positions(campaign)
    ensure_positions_child(campaign, selected.party_character_ids)
    return campaign


def test_migration_adds_reachable_and_rebuilds_connections(tmp_path: Path) -> None:
    campaign_id = "camp_0001"
    campaign_dir = tmp_path / "campaigns" / campaign_id
    campaign_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": campaign_id,
        "selected": {
            "world_id": "world_001",
            "map_id": "map_001",
            "party_character_ids": ["pc_001"],
            "active_actor_id": "pc_001",
        },
        "settings_snapshot": {
            "context": {"full_context_enabled": True, "compress_enabled": False},
            "rules": {"hp_zero_ends_game": True},
            "rollback": {"max_checkpoints": 0},
            "dialog": {"auto_type_enabled": True},
        },
        "settings_revision": 0,
        "allowlist": ["move", "hp_delta", "map_generate"],
        "map": {
            "areas": {
                "area_001": {"id": "area_001", "name": "Start", "parent_area_id": None},
                "area_002": {"id": "area_002", "name": "Side", "parent_area_id": None},
            },
            "connections": [{"from_area_id": "area_001", "to_area_id": "area_002"}],
        },
        "positions": {"pc_001": "area_001"},
        "hp": {"pc_001": 10},
        "character_states": {"pc_001": "alive"},
        "goal": {"text": "Goal", "status": "active"},
        "milestone": {"current": "intro", "last_advanced_turn": 0},
        "created_at": "2026-01-14T00:00:00+00:00",
    }
    campaign_path = campaign_dir / "campaign.json"
    campaign_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    repo = FileRepo(tmp_path)
    campaign = repo.get_campaign(campaign_id)
    assert campaign.map.areas["area_001"].reachable_area_ids == ["area_002"]
    assert campaign.map.areas["area_002"].reachable_area_ids == []

    repo.save_campaign(campaign)
    saved = json.loads(campaign_path.read_text(encoding="utf-8"))
    assert saved["map"]["connections"] == [
        {"from_area_id": "area_001", "to_area_id": "area_002"}
    ]


def test_map_generate_root_layer() -> None:
    map_data = MapData(
        areas={
            "area_001": MapArea(
                id="area_001", name="Root", reachable_area_ids=[]
            )
        },
        connections=[],
    )
    campaign = _make_campaign(map_data)
    call = ToolCall(
        id="call_001",
        tool="map_generate",
        args={
            "parent_area_id": None,
            "theme": "Forest",
            "constraints": {"size": 4, "seed": "alpha"},
        },
    )
    applied_actions, tool_feedback = execute_tool_calls(
        campaign, "pc_001", [call]
    )
    assert tool_feedback is None
    assert len(applied_actions) == 1
    created = applied_actions[0].result["created_area_ids"]
    assert len(created) == 4
    for area_id in created:
        assert campaign.map.areas[area_id].parent_area_id is None
    require_valid_map(campaign.map)


def test_map_generate_child_layer() -> None:
    map_data = MapData(
        areas={
            "area_001": MapArea(
                id="area_001", name="Root", reachable_area_ids=[]
            )
        },
        connections=[],
    )
    campaign = _make_campaign(map_data)
    call = ToolCall(
        id="call_002",
        tool="map_generate",
        args={
            "parent_area_id": "area_001",
            "theme": "Cave",
            "constraints": {"size": 3, "seed": "beta"},
        },
    )
    applied_actions, tool_feedback = execute_tool_calls(
        campaign, "pc_001", [call]
    )
    assert tool_feedback is None
    created = applied_actions[0].result["created_area_ids"]
    entry_id = created[0]
    assert entry_id in campaign.map.areas["area_001"].reachable_area_ids
    for area_id in created:
        assert campaign.map.areas[area_id].parent_area_id == "area_001"
    require_valid_map(campaign.map)


@pytest.mark.parametrize(
    "call_args,allowlist,state,expected_reason",
    [
        ({"parent_area_id": "missing"}, ["map_generate"], "alive", "invalid_args"),
        (
            {"parent_area_id": None, "constraints": {"size": 31}},
            ["map_generate"],
            "alive",
            "invalid_args",
        ),
        ({"parent_area_id": None}, ["move"], "alive", "tool_not_allowed"),
        ({"parent_area_id": None}, ["map_generate"], "dead", "actor_state_restricted"),
    ],
)
def test_map_generate_failure_cases(
    call_args: dict,
    allowlist: list,
    state: str,
    expected_reason: str,
) -> None:
    map_data = MapData(
        areas={
            "area_001": MapArea(
                id="area_001", name="Root", reachable_area_ids=[]
            )
        },
        connections=[],
    )
    campaign = _make_campaign(map_data)
    campaign.allowlist = list(allowlist)
    campaign.character_states["pc_001"] = state
    call = ToolCall(id="call_fail", tool="map_generate", args=call_args)
    applied_actions, tool_feedback = execute_tool_calls(
        campaign, "pc_001", [call]
    )
    assert applied_actions == []
    assert tool_feedback is not None
    assert tool_feedback.failed_calls[0].reason == expected_reason
