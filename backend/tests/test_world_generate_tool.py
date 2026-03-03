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

    def generate(self, system_prompt: str, user_input: str, debug_append: Any) -> Dict[str, Any]:
        return dict(self.payload)


def _make_campaign(campaign_id: str, *, world_id: str) -> Campaign:
    return Campaign(
        id=campaign_id,
        selected=Selected(
            world_id=world_id,
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
                    reachable_area_ids=[],
                )
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


def test_world_generate_creates_world_json_when_missing(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    campaign = _make_campaign("camp_0001", world_id="world_001")
    repo.create_campaign(campaign)

    call = ToolCall(id="call_world_001", tool="world_generate", args={})
    applied_actions, tool_feedback = execute_tool_calls(
        campaign,
        "pc_001",
        [call],
        repo=repo,
    )

    assert tool_feedback is None
    assert len(applied_actions) == 1
    result = applied_actions[0].result
    assert result["world_id"] == "world_001"
    assert result["created"] is True
    assert result["also_generate_map"] is False

    world_path = tmp_path / "storage" / "worlds" / "world_001" / "world.json"
    assert world_path.exists()


def test_world_generate_is_idempotent_for_seed_and_generator(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    campaign = _make_campaign("camp_0002", world_id="world_abc")
    repo.create_campaign(campaign)

    call = ToolCall(
        id="call_world_seed",
        tool="world_generate",
        args={"seed": 424242},
    )
    first_actions, first_feedback = execute_tool_calls(
        campaign,
        "pc_001",
        [call],
        repo=repo,
    )
    assert first_feedback is None
    first_result = first_actions[0].result
    first_world = repo.get_world("world_abc")
    assert first_world is not None

    second_actions, second_feedback = execute_tool_calls(
        campaign,
        "pc_001",
        [call],
        repo=repo,
    )
    assert second_feedback is None
    second_result = second_actions[0].result
    second_world = repo.get_world("world_abc")
    assert second_world is not None

    assert first_result["seed"] == second_result["seed"] == 424242
    assert first_result["generator_id"] == second_result["generator_id"]
    assert second_result["created"] is False
    assert first_world.updated_at == second_world.updated_at


def test_world_generate_bind_to_campaign_persists_selected_world_id(
    tmp_path: Path,
) -> None:
    repo = FileRepo(tmp_path / "storage")
    campaign = _make_campaign("camp_0003", world_id="world_origin")
    repo.create_campaign(campaign)

    call = ToolCall(
        id="call_world_bind",
        tool="world_generate",
        args={"world_id": "world_bound", "bind_to_campaign": True},
    )
    applied_actions, tool_feedback = execute_tool_calls(
        campaign,
        "pc_001",
        [call],
        repo=repo,
    )
    assert tool_feedback is None
    assert len(applied_actions) == 1
    assert applied_actions[0].result["bound_to_campaign"] is True
    assert campaign.selected.world_id == "world_bound"

    repo.save_campaign(campaign)
    reloaded = repo.get_campaign("camp_0003")
    assert reloaded.selected.world_id == "world_bound"


def test_world_generate_bind_persists_via_turn_service_flow(
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
                        "id": "call_world_bind_turn",
                        "tool": "world_generate",
                        "args": {"world_id": "world_bound_turn", "bind_to_campaign": True},
                    }
                ],
            }
        ),
    )
    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)
    campaign = _make_campaign("camp_0005", world_id="world_origin")
    repo.create_campaign(campaign)

    result = service.submit_turn("camp_0005", "bind world")
    assert result["tool_feedback"] is None

    reloaded = repo.get_campaign("camp_0005")
    assert reloaded.selected.world_id == "world_bound_turn"


def test_world_generate_returns_world_id_missing_when_unbound(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    campaign = _make_campaign("camp_0004", world_id="")
    repo.create_campaign(campaign)

    call = ToolCall(id="call_world_missing", tool="world_generate", args={})
    applied_actions, tool_feedback = execute_tool_calls(
        campaign,
        "pc_001",
        [call],
        repo=repo,
    )

    assert applied_actions == []
    assert tool_feedback is not None
    assert tool_feedback.failed_calls[0].status == "error"
    assert tool_feedback.failed_calls[0].reason == "world_id_missing"
