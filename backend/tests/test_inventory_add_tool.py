from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

import backend.app.turn_service as turn_service_module
from backend.app.tool_executor import execute_tool_calls
from backend.app.turn_service import TurnService
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
from backend.infra.file_repo import FileRepo


class _StubLLM:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self.payload = payload

    def generate(
        self, system_prompt: str, user_input: str, debug_append: Any
    ) -> Dict[str, Any]:
        return dict(self.payload)


def _make_campaign(campaign_id: str = "camp_inventory") -> Campaign:
    return Campaign(
        id=campaign_id,
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001"],
            active_actor_id="pc_001",
        ),
        settings_snapshot=SettingsSnapshot(),
        goal=Goal(text="Find one useful item.", status="active"),
        milestone=Milestone(current="intro", last_advanced_turn=0),
        map=MapData(
            areas={
                "area_001": MapArea(
                    id="area_001",
                    name="Start",
                    description="A plain start room.",
                    reachable_area_ids=["area_002"],
                ),
                "area_002": MapArea(
                    id="area_002",
                    name="Side Room",
                    description="A narrow side room.",
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
            )
        },
    )


def _add_inventory_source(
    campaign: Campaign,
    *,
    source_entity_id: str,
    item_id: str,
    quantity: int = 1,
    area_id: str = "area_001",
) -> None:
    campaign.entities[source_entity_id] = Entity(
        id=source_entity_id,
        kind="object",
        label=f"{item_id} source",
        tags=["loot_source"],
        loc=EntityLocation(type="area", id=area_id),
        verbs=["inspect", "search"],
        state={
            "inventory_item_id": item_id,
            "inventory_quantity": quantity,
            "inventory_granted": False,
        },
        props={},
    )


def test_inventory_add_applies_and_updates_actor_inventory() -> None:
    campaign = _make_campaign()
    _add_inventory_source(campaign, source_entity_id="torch_cache", item_id="torch", quantity=2)
    call = ToolCall(
        id="call_inventory_001",
        tool="inventory_add",
        args={"item_id": "torch", "quantity": 2, "source_entity_id": "torch_cache"},
    )

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert tool_feedback is None
    assert len(applied_actions) == 1
    action = applied_actions[0]
    assert action.tool == "inventory_add"
    assert action.result == {
        "actor_id": "pc_001",
        "item_id": "torch",
        "quantity_added": 2,
        "new_quantity": 2,
    }
    assert campaign.actors["pc_001"].inventory["torch"] == 2
    assert campaign.positions == {}
    assert campaign.hp == {}
    assert campaign.character_states == {}
    assert campaign.state.positions == {}
    assert campaign.state.positions_parent == {}
    assert campaign.state.positions_child == {}


@pytest.mark.parametrize(
    ("args", "expected_reason"),
    [
        ({"item_id": "", "quantity": 1}, "invalid_args"),
        ({"item_id": "rope", "quantity": 0}, "invalid_args"),
        ({"item_id": "rope", "quantity": -1}, "invalid_args"),
        ({"item_id": "rope", "quantity": "2"}, "invalid_args"),
        ({"item_id": "rope", "quantity": 1}, "inventory_source_required"),
        (
            {"item_id": "rope", "quantity": 1, "source_entity_id": "missing_source"},
            "invalid_item_source",
        ),
        ({"item_id": "rope", "actor_id": "pc_999"}, "actor_context_mismatch"),
    ],
)
def test_inventory_add_rejects_invalid_args(
    args: Dict[str, Any], expected_reason: str
) -> None:
    campaign = _make_campaign()
    call = ToolCall(id="call_inventory_bad", tool="inventory_add", args=args)

    applied_actions, tool_feedback = execute_tool_calls(campaign, "pc_001", [call])

    assert applied_actions == []
    assert tool_feedback is not None
    assert tool_feedback.failed_calls[0].reason == expected_reason
    assert campaign.actors["pc_001"].inventory == {}


def test_inventory_add_persists_via_turn_service(
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
                        "id": "call_inventory_turn",
                        "tool": "inventory_add",
                        "args": {
                            "item_id": "medkit",
                            "quantity": 1,
                            "source_entity_id": "medkit_cache",
                        },
                    }
                ],
            }
        ),
    )

    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)
    campaign = _make_campaign("camp_inventory_turn")
    _add_inventory_source(
        campaign, source_entity_id="medkit_cache", item_id="medkit", quantity=1
    )
    repo.create_campaign(campaign)

    response = service.submit_turn("camp_inventory_turn", "Pick up the medkit.")

    assert response["tool_feedback"] is None
    assert len(response["applied_actions"]) == 1
    assert response["applied_actions"][0]["tool"] == "inventory_add"
    assert response["state_summary"]["active_actor_inventory"] == {"medkit": 1}
    reloaded = repo.get_campaign("camp_inventory_turn")
    payload = json.loads(
        (tmp_path / "storage" / "campaigns" / "camp_inventory_turn" / "campaign.json").read_text(
            encoding="utf-8"
        )
    )
    assert reloaded.actors["pc_001"].inventory == {"medkit": 1}
    assert reloaded.positions == {}
    assert reloaded.hp == {}
    assert reloaded.character_states == {}
    assert reloaded.state.positions == {}
    assert reloaded.state.positions_parent == {}
    assert reloaded.state.positions_child == {}
    assert payload["positions"] == {}
    assert payload["hp"] == {}
    assert payload["character_states"] == {}
    assert payload["state"]["positions"] == {}
    assert payload["state"]["positions_parent"] == {}
    assert payload["state"]["positions_child"] == {}


def test_regular_turn_does_not_change_inventory_without_inventory_add(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        turn_service_module,
        "LLMClient",
        lambda: _StubLLM(
            {
                "assistant_text": "You pause and observe the room.",
                "dialog_type": "scene_description",
                "tool_calls": [],
            }
        ),
    )

    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)
    campaign = _make_campaign("camp_inventory_narrative")
    campaign.actors["pc_001"].inventory = {"torch": 1}
    repo.create_campaign(campaign)

    response = service.submit_turn(
        "camp_inventory_narrative",
        "Describe the current scene without calling tools.",
    )

    assert response["applied_actions"] == []
    assert response["state_summary"]["active_actor_inventory"] == {"torch": 1}
    reloaded = repo.get_campaign("camp_inventory_narrative")
    assert reloaded.actors["pc_001"].inventory == {"torch": 1}


def test_free_form_turn_cannot_add_apple_without_authoritative_source(
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
                        "id": "call_inventory_apple",
                        "tool": "inventory_add",
                        "args": {"item_id": "apple", "quantity": 1},
                    }
                ],
            }
        ),
    )

    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)
    repo.create_campaign(_make_campaign("camp_inventory_apple"))

    response = service.submit_turn("camp_inventory_apple", "add an apple to my inventory")

    assert response["applied_actions"] == []
    assert response["tool_feedback"]["failed_calls"] == [
        {
            "id": "call_inventory_apple",
            "tool": "inventory_add",
            "status": "error",
            "reason": "inventory_source_required",
        }
    ]
    assert response["state_summary"]["active_actor_inventory"] == {}


def test_free_form_turn_cannot_add_tower_key_without_authoritative_source(
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
                        "id": "call_inventory_tower_key",
                        "tool": "inventory_add",
                        "args": {"item_id": "tower_key", "quantity": 1},
                    }
                ],
            }
        ),
    )

    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)
    repo.create_campaign(_make_campaign("camp_inventory_tower_key"))

    response = service.submit_turn("camp_inventory_tower_key", "add tower_key to my inventory")

    assert response["applied_actions"] == []
    assert response["tool_feedback"]["failed_calls"] == [
        {
            "id": "call_inventory_tower_key",
            "tool": "inventory_add",
            "status": "error",
            "reason": "inventory_source_required",
        }
    ]
    assert response["state_summary"]["active_actor_inventory"] == {}
