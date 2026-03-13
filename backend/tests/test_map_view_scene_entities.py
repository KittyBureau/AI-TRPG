from __future__ import annotations

import backend.app.turn_service as turn_service_module

from pathlib import Path
from typing import Any, Dict

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.app.item_runtime import create_runtime_item_stack
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
)
from backend.infra.file_repo import FileRepo


class _OpenCrateLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        return {
            "assistant_text": "",
            "dialog_type": "scene_description",
            "tool_calls": [
                {
                    "id": "call_scene_open",
                    "tool": "scene_action",
                    "args": {
                        "actor_id": "pc_001",
                        "action": "open",
                        "target_id": "crate_01",
                        "params": {},
                    },
                }
            ],
        }


class _TakeAppleLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        return {
            "assistant_text": "",
            "dialog_type": "scene_description",
            "tool_calls": [
                {
                    "id": "call_scene_take",
                    "tool": "scene_action",
                    "args": {
                        "actor_id": "pc_001",
                        "action": "take",
                        "target_id": "apple_01",
                        "params": {},
                    },
                }
            ],
        }


def _seed_campaign(tmp_path: Path, campaign_id: str) -> None:
    repo = FileRepo(tmp_path / "storage")
    campaign = Campaign(
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
                "area_001": MapArea(id="area_001", name="Start", reachable_area_ids=["area_002"]),
                "area_002": MapArea(id="area_002", name="Side", reachable_area_ids=[]),
            },
            connections=[],
        ),
        actors={
            "pc_001": ActorState(position="area_001", hp=10, character_state="alive", meta={})
        },
        entities={
            "apple_01": Entity(
                id="apple_01",
                kind="item",
                label="Apple",
                tags=["loot"],
                loc=EntityLocation(type="area", id="area_001"),
                verbs=["inspect", "take"],
                state={},
                props={},
            ),
            "crate_01": Entity(
                id="crate_01",
                kind="container",
                label="Supply Crate",
                tags=["container"],
                loc=EntityLocation(type="area", id="area_001"),
                verbs=["inspect", "open", "search"],
                state={"opened": False},
                props={},
            ),
            "coin_01": Entity(
                id="coin_01",
                kind="item",
                label="Coin",
                tags=["loot"],
                loc=EntityLocation(type="area", id="area_002"),
                verbs=["inspect", "take"],
                state={},
                props={},
            ),
        },
    )
    repo.create_campaign(campaign)


def _client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    llm_class: type | None = None,
) -> TestClient:
    monkeypatch.chdir(tmp_path)
    if llm_class is not None:
        monkeypatch.setattr(turn_service_module, "LLMClient", llm_class)
    return TestClient(create_app())


def test_map_view_returns_only_current_area_entities_from_campaign_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign_id = "camp_map_scene"
    _seed_campaign(tmp_path, campaign_id)
    client = _client(tmp_path, monkeypatch)

    response = client.get(
        "/api/v1/map/view",
        params={"campaign_id": campaign_id, "actor_id": "pc_001"},
    )
    assert response.status_code == 200
    payload = response.json()
    entities = payload["entities_in_area"]
    assert isinstance(entities, list)
    assert [entity["id"] for entity in entities] == ["apple_01", "crate_01"]
    assert entities[0]["state"] == {}
    assert entities[1]["state"] == {"opened": False}
    assert all(entity["id"] != "coin_01" for entity in entities)


def test_map_view_does_not_surface_area_item_stacks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign_id = "camp_map_scene_items_hidden"
    _seed_campaign(tmp_path, campaign_id)
    repo = FileRepo(tmp_path / "storage")
    campaign = repo.get_campaign(campaign_id)
    ration_stack = create_runtime_item_stack(
        definition_id="field_ration",
        quantity=1,
        parent_type="area",
        parent_id="area_001",
        label="Field Ration",
        stack_id_salt="test_map_scene:hidden_area_stack",
    )
    campaign.items = {ration_stack.stack_id: ration_stack}
    repo.save_campaign(campaign)
    client = _client(tmp_path, monkeypatch)

    response = client.get(
        "/api/v1/map/view",
        params={"campaign_id": campaign_id, "actor_id": "pc_001"},
    )
    assert response.status_code == 200
    entities = response.json()["entities_in_area"]
    assert [entity["id"] for entity in entities] == ["apple_01", "crate_01"]
    assert all(entity["id"] != "field_ration" for entity in entities)


def test_map_view_reflects_entity_state_changes_from_scene_action_turn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign_id = "camp_map_scene_state"
    _seed_campaign(tmp_path, campaign_id)
    client = _client(tmp_path, monkeypatch, _OpenCrateLLM)

    turn_response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": campaign_id,
            "user_input": "[UI_FLOW_STEP] open crate",
            "execution": {"actor_id": "pc_001"},
        },
    )
    assert turn_response.status_code == 200
    assert turn_response.json()["applied_actions"][0]["tool"] == "scene_action"

    map_response = client.get(
        "/api/v1/map/view",
        params={"campaign_id": campaign_id, "actor_id": "pc_001"},
    )
    assert map_response.status_code == 200
    entities_by_id = {
        entity["id"]: entity for entity in map_response.json()["entities_in_area"]
    }
    assert entities_by_id["crate_01"]["state"] == {"opened": True}


def test_map_view_reflects_entity_location_changes_from_scene_action_turn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign_id = "camp_map_scene_location"
    _seed_campaign(tmp_path, campaign_id)
    client = _client(tmp_path, monkeypatch, _TakeAppleLLM)

    turn_response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": campaign_id,
            "user_input": "[UI_FLOW_STEP] take apple",
            "execution": {"actor_id": "pc_001"},
        },
    )
    assert turn_response.status_code == 200
    assert turn_response.json()["applied_actions"][0]["tool"] == "scene_action"

    map_response = client.get(
        "/api/v1/map/view",
        params={"campaign_id": campaign_id, "actor_id": "pc_001"},
    )
    assert map_response.status_code == 200
    assert [entity["id"] for entity in map_response.json()["entities_in_area"]] == [
        "crate_01"
    ]
