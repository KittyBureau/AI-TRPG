from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import backend.app.turn_service as turn_service_module
from backend.api.main import create_app
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


class _StubSceneActionLLM:
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


class _NarrativeOnlyLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        return {
            "assistant_text": "The room is quiet.",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }


def _create_campaign(tmp_path: Path, campaign_id: str) -> None:
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
        goal=Goal(text="Collect one coin.", status="active"),
        milestone=Milestone(current="intro", last_advanced_turn=0),
        map=MapData(
            areas={
                "area_001": MapArea(
                    id="area_001",
                    name="Start",
                    description="Start room.",
                    reachable_area_ids=["area_002"],
                ),
                "area_002": MapArea(
                    id="area_002",
                    name="Side",
                    description="Side room.",
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
        entities={
            "crate_01": Entity(
                id="crate_01",
                kind="container",
                label="Supply Crate",
                tags=["container"],
                loc=EntityLocation(type="area", id="area_001"),
                verbs=["inspect", "open", "search"],
                state={"opened": False},
                props={"mass": 8},
            )
        },
    )
    repo.create_campaign(campaign)


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(turn_service_module, "LLMClient", _StubSceneActionLLM)
    return TestClient(create_app())


def test_chat_turn_scene_action_updates_campaign_entities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign_id = "camp_scene_turn"
    _create_campaign(tmp_path, campaign_id)
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": campaign_id,
            "user_input": "[UI_FLOW_STEP] scene action take",
            "execution": {"actor_id": "pc_001"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["effective_actor_id"] == "pc_001"
    assert payload["applied_actions"][0]["tool"] == "scene_action"
    assert payload["applied_actions"][0]["result"]["ok"] is True
    assert payload["applied_actions"][0]["result"]["patches"]["entity_patches"] == [
        {
            "id": "crate_01",
            "changes": {
                "state": {"opened": True},
            },
        }
    ]

    campaign_path = tmp_path / "storage" / "campaigns" / campaign_id / "campaign.json"
    data = json.loads(campaign_path.read_text(encoding="utf-8"))
    assert data["actors"]["pc_001"]["position"] == "area_001"
    assert data["entities"]["crate_01"]["loc"]["type"] == "area"
    assert data["entities"]["crate_01"]["loc"]["id"] == "area_001"
    assert data["entities"]["crate_01"]["state"]["opened"] is True


def test_chat_turn_without_tools_does_not_change_actor_position(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign_id = "camp_narrative_turn"
    _create_campaign(tmp_path, campaign_id)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(turn_service_module, "LLMClient", _NarrativeOnlyLLM)
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": campaign_id,
            "user_input": "Describe the current scene without calling tools.",
            "execution": {"actor_id": "pc_001"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["applied_actions"] == []

    campaign_path = tmp_path / "storage" / "campaigns" / campaign_id / "campaign.json"
    data = json.loads(campaign_path.read_text(encoding="utf-8"))
    assert data["actors"]["pc_001"]["position"] == "area_001"
