from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

import backend.app.turn_service as turn_service_module
from backend.app.tool_executor import execute_tool_calls
from backend.app.turn_service import TurnService
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


class _StubLLM:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self.payload = payload

    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        return dict(self.payload)


def _make_campaign(campaign_id: str = "camp_spawn") -> Campaign:
    return Campaign(
        id=campaign_id,
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001"],
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
                    name="Side Room",
                    reachable_area_ids=[],
                ),
            },
            connections=[],
        ),
        actors={
            "pc_001": ActorState(
                position="area_002",
                hp=10,
                character_state="alive",
                meta={},
            )
        },
    )


def test_actor_spawn_creates_actor_and_binds_to_party_by_default() -> None:
    campaign = _make_campaign()
    call = ToolCall(
        id="call_spawn_001",
        tool="actor_spawn",
        args={"character_id": "char_knight"},
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    actor_id = result["actor_id"]
    assert actor_id.startswith("actor_")
    assert result["position"] == "area_002"
    assert result["hp"] == 10
    assert result["created"] is True

    actor = campaign.actors[actor_id]
    assert actor.character_state == "alive"
    assert actor.meta["character_id"] == "char_knight"
    assert actor_id in campaign.selected.party_character_ids


def test_actor_spawn_bind_to_party_false_does_not_change_party() -> None:
    campaign = _make_campaign()
    original_party = list(campaign.selected.party_character_ids)
    call = ToolCall(
        id="call_spawn_002",
        tool="actor_spawn",
        args={"character_id": "char_mage", "bind_to_party": False},
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    actor_id = applied_actions[0].result["actor_id"]
    assert actor_id in campaign.actors
    assert campaign.selected.party_character_ids == original_party


def test_actor_spawn_spawn_position_rules() -> None:
    campaign = _make_campaign()
    valid = ToolCall(
        id="call_spawn_003",
        tool="actor_spawn",
        args={"character_id": "char_archer", "spawn_position": "area_001"},
    )

    valid_actions, valid_feedback = execute_tool_calls(campaign, "pc_001", [valid])
    assert valid_feedback is None
    assert valid_actions[0].result["position"] == "area_001"

    before_count = len(campaign.actors)
    invalid = ToolCall(
        id="call_spawn_004",
        tool="actor_spawn",
        args={"character_id": "char_rogue", "spawn_position": "area_missing"},
    )
    invalid_actions, invalid_feedback = execute_tool_calls(campaign, "pc_001", [invalid])
    assert invalid_actions == []
    assert invalid_feedback is not None
    assert invalid_feedback.failed_calls[0].reason == "invalid_args"
    assert len(campaign.actors) == before_count


def test_actor_spawn_sets_active_actor_when_active_is_empty() -> None:
    campaign = _make_campaign()
    campaign.selected.active_actor_id = ""
    call = ToolCall(
        id="call_spawn_005",
        tool="actor_spawn",
        args={"character_id": "char_healer"},
    )

    actions, feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert feedback is None
    actor_id = actions[0].result["actor_id"]
    assert campaign.selected.active_actor_id == actor_id


def test_actor_spawn_persists_via_turn_service_flow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        turn_service_module,
        "LLMClient",
        lambda: _StubLLM(
            {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_spawn_turn",
                        "tool": "actor_spawn",
                        "args": {"character_id": "char_turn"},
                    }
                ],
            }
        ),
    )
    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)
    campaign = _make_campaign("camp_spawn_turn")
    repo.create_campaign(campaign)

    response = service.submit_turn("camp_spawn_turn", "spawn actor")

    assert response["tool_feedback"] is None
    assert len(response["applied_actions"]) == 1
    spawned_actor_id = response["applied_actions"][0]["result"]["actor_id"]
    reloaded = repo.get_campaign("camp_spawn_turn")
    assert spawned_actor_id in reloaded.actors
    assert spawned_actor_id in reloaded.selected.party_character_ids
