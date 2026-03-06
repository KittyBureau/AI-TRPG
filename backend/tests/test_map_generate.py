from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

import backend.app.tool_executor as tool_executor_module
from backend.app.tool_executor import execute_tool_calls
from backend.domain.map_models import require_valid_map
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
from backend.infra.file_repo import FileRepo
from backend.infra.map_generators.deterministic_generator import MapGenerationResult


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
    assert "pc_001" in campaign.actors

    repo.save_campaign(campaign)
    saved = json.loads(campaign_path.read_text(encoding="utf-8"))
    assert saved["map"]["connections"] == [
        {"from_area_id": "area_001", "to_area_id": "area_002"}
    ]
    assert "actors" in saved


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
        assert "area_001" in campaign.map.areas[area_id].reachable_area_ids
        assert area_id in campaign.map.areas["area_001"].reachable_area_ids
    require_valid_map(campaign.map)


def test_map_generate_updates_only_map_authority() -> None:
    map_data = MapData(
        areas={
            "area_001": MapArea(
                id="area_001", name="Root", reachable_area_ids=[]
            )
        },
        connections=[],
    )
    campaign = _make_campaign(map_data)
    campaign.selected.world_id = "world_keep"
    campaign.settings_revision = 9
    campaign.actors["pc_001"].inventory = {"rope": 1}
    before_selected = deepcopy(campaign.selected)
    before_actor = deepcopy(campaign.actors["pc_001"])
    before_goal = deepcopy(campaign.goal)
    before_milestone = deepcopy(campaign.milestone)
    call = ToolCall(
        id="call_authority",
        tool="map_generate",
        args={
            "parent_area_id": "area_001",
            "theme": "Authority",
            "constraints": {"size": 2, "seed": "authority"},
        },
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    assert campaign.selected == before_selected
    assert campaign.actors["pc_001"] == before_actor
    assert campaign.goal == before_goal
    assert campaign.milestone == before_milestone
    assert campaign.settings_revision == 9
    require_valid_map(campaign.map)
    for connection in campaign.map.connections:
        assert connection.from_area_id in campaign.map.areas
        assert connection.to_area_id in campaign.map.areas


def test_map_generate_invalid_graph_rolls_back_state(
    monkeypatch: pytest.MonkeyPatch,
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
    before_map = deepcopy(campaign.map)
    before_selected = deepcopy(campaign.selected)
    before_actor = deepcopy(campaign.actors["pc_001"])

    class _BadGraphGenerator:
        def generate(self, existing_map, parent_area_id, theme, size, seed):
            return MapGenerationResult(
                new_areas={
                    "area_002": MapArea(
                        id="area_002",
                        name="Broken",
                        reachable_area_ids=[],
                    )
                },
                new_edges=[("area_002", "area_missing")],
                created_area_ids=["area_002"],
                warnings=[],
                entry_area_id=None,
            )

    monkeypatch.setattr(
        tool_executor_module,
        "DeterministicMapGenerator",
        _BadGraphGenerator,
    )
    call = ToolCall(
        id="call_bad_graph",
        tool="map_generate",
        args={"parent_area_id": None, "theme": "Broken", "constraints": {"size": 1}},
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert applied_actions == []
    assert tool_feedback is not None
    assert tool_feedback.failed_calls[0].reason == "invalid_args"
    assert campaign.map == before_map
    assert campaign.selected == before_selected
    assert campaign.actors["pc_001"] == before_actor


def test_map_generate_exception_rolls_back_state(
    monkeypatch: pytest.MonkeyPatch,
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
    before_map = deepcopy(campaign.map)
    before_selected = deepcopy(campaign.selected)
    before_actor = deepcopy(campaign.actors["pc_001"])

    class _ExplodingGenerator:
        def generate(self, existing_map, parent_area_id, theme, size, seed):
            raise RuntimeError("boom")

    monkeypatch.setattr(
        tool_executor_module,
        "DeterministicMapGenerator",
        _ExplodingGenerator,
    )
    call = ToolCall(
        id="call_boom",
        tool="map_generate",
        args={"parent_area_id": None, "theme": "Broken", "constraints": {"size": 1}},
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert applied_actions == []
    assert tool_feedback is not None
    assert tool_feedback.failed_calls[0].reason == "invalid_args"
    assert campaign.map == before_map
    assert campaign.selected == before_selected
    assert campaign.actors["pc_001"] == before_actor


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
    campaign.actors["pc_001"].character_state = state
    call = ToolCall(id="call_fail", tool="map_generate", args=call_args)
    applied_actions, tool_feedback = execute_tool_calls(
        campaign, "pc_001", [call]
    )
    assert applied_actions == []
    assert tool_feedback is not None
    assert tool_feedback.failed_calls[0].reason == expected_reason
