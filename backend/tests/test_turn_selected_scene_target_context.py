from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import backend.app.turn_service as turn_service_module
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


class _SceneTargetCaptureLLM:
    last_system_prompt = ""

    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        _SceneTargetCaptureLLM.last_system_prompt = system_prompt
        if user_input == "Inspect the selected target.":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_inspect_selected_target",
                        "tool": "scene_action",
                        "args": {
                            "actor_id": "pc_001",
                            "action": "inspect",
                            "target_id": "apple_01",
                            "params": {},
                        },
                    }
                ],
            }
        if user_input == "Talk to the selected target.":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_talk_selected_target",
                        "tool": "scene_action",
                        "args": {
                            "actor_id": "pc_001",
                            "action": "talk",
                            "target_id": "crate_01",
                            "params": {},
                        },
                    }
                ],
            }
        if user_input == "Use the selected target.":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_use_selected_target",
                        "tool": "scene_action",
                        "args": {
                            "actor_id": "pc_001",
                            "action": "use",
                            "target_id": "crate_01",
                            "params": {},
                        },
                    }
                ],
            }
        return {
            "assistant_text": "Selected scene target context checked.",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }


def _extract_prompt_context(system_prompt: str) -> Dict[str, Any]:
    marker = "Context: "
    if marker not in system_prompt:
        return {}
    return json.loads(system_prompt.rsplit(marker, 1)[1])


def _seed_campaign(tmp_path: Path, campaign_id: str, *, trace_enabled: bool = True) -> str:
    repo = FileRepo(tmp_path / "storage")
    settings_snapshot = SettingsSnapshot()
    settings_snapshot.dialog.turn_profile_trace_enabled = trace_enabled
    ration_stack = create_runtime_item_stack(
        stack_id="stk_ration_area_01",
        definition_id="field_ration",
        quantity=1,
        parent_type="area",
        parent_id="area_001",
        label="Field Ration",
        stack_id_salt=f"{campaign_id}:field_ration",
    )
    campaign = Campaign(
        id=campaign_id,
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001"],
            active_actor_id="pc_001",
        ),
        settings_snapshot=settings_snapshot,
        goal=Goal(text="Pick up the right thing.", status="active"),
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
                    name="Side Room",
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
        items={ration_stack.stack_id: ration_stack},
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
            "crate_01": Entity(
                id="crate_01",
                kind="container",
                label="Crate",
                tags=["container"],
                loc=EntityLocation(type="area", id="area_001"),
                verbs=["inspect", "open", "search"],
                state={"opened": False},
                props={},
            ),
            "guide_01": Entity(
                id="guide_01",
                kind="npc",
                label="Guide",
                tags=["npc"],
                loc=EntityLocation(type="area", id="area_001"),
                verbs=["inspect", "talk"],
                state={},
                props={},
            ),
            "lever_01": Entity(
                id="lever_01",
                kind="object",
                label="Lever",
                tags=["mechanism"],
                loc=EntityLocation(type="area", id="area_001"),
                verbs=["inspect", "use"],
                state={},
                props={},
            ),
            "statue_01": Entity(
                id="statue_01",
                kind="object",
                label="Statue",
                tags=["scenery"],
                loc=EntityLocation(type="area", id="area_001"),
                verbs=[],
                state={},
                props={},
            ),
        },
    )
    repo.create_campaign(campaign)
    return ration_stack.stack_id


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(turn_service_module, "LLMClient", _SceneTargetCaptureLLM)
    _SceneTargetCaptureLLM.last_system_prompt = ""
    return TestClient(create_app())


def test_chat_turn_injects_selected_scene_target_for_visible_area_stack(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stack_id = _seed_campaign(tmp_path, "camp_selected_scene_target_stack")
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": "camp_selected_scene_target_stack",
            "user_input": "Take the selected item.",
            "execution": {"actor_id": "pc_001"},
            "context_hints": {"selected_target_id": stack_id},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["debug"]["selected_scene_target"] == {
        "id": stack_id,
        "kind": "item",
        "label": "Field Ration",
        "source": "area_stack",
        "item_id": "field_ration",
    }
    context = _extract_prompt_context(_SceneTargetCaptureLLM.last_system_prompt)
    assert context["selected_scene_target"] == {
        "id": stack_id,
        "kind": "item",
        "label": "Field Ration",
        "source": "area_stack",
        "item_id": "field_ration",
    }


def test_chat_turn_injects_selected_scene_target_for_visible_takeable_entity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_campaign(tmp_path, "camp_selected_scene_target_entity")
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": "camp_selected_scene_target_entity",
            "user_input": "Pick up the selected object.",
            "execution": {"actor_id": "pc_001"},
            "context_hints": {"selected_target_id": "apple_01"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["debug"]["selected_scene_target"] == {
        "id": "apple_01",
        "kind": "item",
        "label": "Apple",
        "source": "entity",
    }
    context = _extract_prompt_context(_SceneTargetCaptureLLM.last_system_prompt)
    assert context["selected_scene_target"] == {
        "id": "apple_01",
        "kind": "item",
        "label": "Apple",
        "source": "entity",
    }


def test_chat_turn_inspect_uses_selected_scene_target_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_campaign(tmp_path, "camp_selected_scene_target_inspect")
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": "camp_selected_scene_target_inspect",
            "user_input": "Inspect the selected target.",
            "execution": {"actor_id": "pc_001"},
            "context_hints": {"selected_target_id": "crate_01"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["applied_actions"][0]["tool"] == "scene_action"
    assert payload["applied_actions"][0]["args"]["action"] == "inspect"
    assert payload["applied_actions"][0]["args"]["target_id"] == "crate_01"
    assert "crate" in payload["narrative_text"].lower()


def test_chat_turn_talk_uses_selected_scene_target_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_campaign(tmp_path, "camp_selected_scene_target_talk")
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": "camp_selected_scene_target_talk",
            "user_input": "Talk to the selected target.",
            "execution": {"actor_id": "pc_001"},
            "context_hints": {"selected_target_id": "guide_01"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["applied_actions"][0]["tool"] == "scene_action"
    assert payload["applied_actions"][0]["args"]["action"] == "talk"
    assert payload["applied_actions"][0]["args"]["target_id"] == "guide_01"
    assert "guide" in payload["narrative_text"].lower()


def test_chat_turn_use_uses_selected_scene_target_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_campaign(tmp_path, "camp_selected_scene_target_use")
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": "camp_selected_scene_target_use",
            "user_input": "Use the selected target.",
            "execution": {"actor_id": "pc_001"},
            "context_hints": {"selected_target_id": "lever_01"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["applied_actions"][0]["tool"] == "scene_action"
    assert payload["applied_actions"][0]["args"]["action"] == "use"
    assert payload["applied_actions"][0]["args"]["target_id"] == "lever_01"
    assert "lever" in payload["narrative_text"].lower()


def test_chat_turn_rejects_selected_scene_target_when_not_interactable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_campaign(tmp_path, "camp_selected_scene_target_invalid")
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": "camp_selected_scene_target_invalid",
            "user_input": "Inspect the selected target.",
            "execution": {"actor_id": "pc_001"},
            "context_hints": {"selected_target_id": "statue_01"},
        },
    )

    assert response.status_code == 400
    assert "selected_target_id is not interactable in the current area" in response.json()["detail"]
