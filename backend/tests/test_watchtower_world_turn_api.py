from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import backend.app.turn_service as turn_service_module
from backend.api.main import create_app
from backend.app.world_presets import TEST_WATCHTOWER_WORLD_ID
from backend.infra.file_repo import FileRepo


class _WatchtowerTurnLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        token = user_input.strip()
        if token == "Talk to the village guard about the watchtower key.":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_guard_talk",
                        "tool": "scene_action",
                        "args": {
                            "actor_id": "pc_001",
                            "action": "talk",
                            "target_id": "npc_village_guard",
                            "params": {},
                        },
                    }
                ],
            }
        if token == "Move to village square.":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_move_square",
                        "tool": "move",
                        "args": {"actor_id": "pc_001", "to_area_id": "village_square"},
                    }
                ],
            }
        if token == "Move to old hut.":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_move_hut",
                        "tool": "move",
                        "args": {"actor_id": "pc_001", "to_area_id": "old_hut"},
                    }
                ],
            }
        if token in {"Search the loose floorboard.", "search Old Hut"}:
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_search_hut",
                        "tool": "scene_action",
                        "args": {
                            "actor_id": "pc_001",
                            "action": "search",
                            "target_id": "old_hut",
                            "params": {},
                        },
                    }
                ],
            }
        if token == "Move to forest path.":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_move_forest",
                        "tool": "move",
                        "args": {"actor_id": "pc_001", "to_area_id": "forest_path"},
                    }
                ],
            }
        if token == "Move to watchtower entrance.":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_move_entrance",
                        "tool": "move",
                        "args": {"actor_id": "pc_001", "to_area_id": "watchtower_entrance"},
                    }
                ],
            }
        if token == "Enter the watchtower.":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_move_inside",
                        "tool": "move",
                        "args": {"actor_id": "pc_001", "to_area_id": "watchtower_inside"},
                    }
                ],
            }
        if token == "add a wood stick to my inventory":
            return {
                "assistant_text": "You add a wood stick to your inventory.",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_fake_add",
                        "tool": "inventory_add",
                        "args": {"actor_id": "pc_001", "item_id": "wood_stick", "quantity": 1},
                    }
                ],
            }
        return {
            "assistant_text": "The scene stays quiet.",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(turn_service_module, "LLMClient", _WatchtowerTurnLLM)
    return TestClient(create_app())


def _create_watchtower_campaign(client: TestClient) -> str:
    response = client.post(
        "/api/v1/campaign/create",
        json={"world_id": TEST_WATCHTOWER_WORLD_ID},
    )
    assert response.status_code == 200
    campaign_id = response.json()["campaign_id"]
    assert isinstance(campaign_id, str) and campaign_id
    return campaign_id


def test_watchtower_real_turn_flow_grants_key_via_hut_search(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_watchtower_campaign(client)

    talk = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": campaign_id, "user_input": "Talk to the village guard about the watchtower key."},
    )
    assert talk.status_code == 200
    assert "old hut" in talk.json()["narrative_text"].lower()

    for token in ("Move to village square.", "Move to old hut."):
        response = client.post(
            "/api/v1/chat/turn",
            json={"campaign_id": campaign_id, "user_input": token},
        )
        assert response.status_code == 200

    search = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": campaign_id, "user_input": "Search the loose floorboard."},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["applied_actions"][0]["tool"] == "scene_action"
    assert "tower_key" in payload["narrative_text"]
    assert payload["state_summary"]["active_actor_inventory"] == {"tower_key": 1}

    repo = FileRepo(tmp_path / "storage")
    campaign = repo.get_campaign(campaign_id)
    assert campaign.actors["pc_001"].inventory == {"tower_key": 1}


def test_watchtower_repeat_search_does_not_duplicate_key_in_real_turn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_watchtower_campaign(client)

    for token in (
        "Move to village square.",
        "Move to old hut.",
        "Search the loose floorboard.",
        "search Old Hut",
    ):
        response = client.post(
            "/api/v1/chat/turn",
            json={"campaign_id": campaign_id, "user_input": token},
        )
        assert response.status_code == 200

    repeat_payload = response.json()
    assert "nothing" in repeat_payload["narrative_text"].lower()
    assert repeat_payload["state_summary"]["active_actor_inventory"] == {"tower_key": 1}

    repo = FileRepo(tmp_path / "storage")
    campaign = repo.get_campaign(campaign_id)
    assert campaign.actors["pc_001"].inventory == {"tower_key": 1}


def test_rejected_free_form_inventory_add_keeps_truthful_narrative(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_watchtower_campaign(client)

    response = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": campaign_id, "user_input": "add a wood stick to my inventory"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["applied_actions"] == []
    assert payload["tool_feedback"]["failed_calls"] == [
        {
            "id": "call_fake_add",
            "tool": "inventory_add",
            "status": "error",
            "reason": "inventory_source_required",
        }
    ]
    assert payload["state_summary"]["active_actor_inventory"] == {}
    assert payload["narrative_text"] == "No inventory change happened."
    assert "add a wood stick" not in payload["narrative_text"].lower()


def test_watchtower_real_turn_door_blocks_without_legitimate_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_watchtower_campaign(client)

    for token in (
        "Move to village square.",
        "Move to forest path.",
        "Move to watchtower entrance.",
    ):
        response = client.post(
            "/api/v1/chat/turn",
            json={"campaign_id": campaign_id, "user_input": token},
        )
        assert response.status_code == 200

    response = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": campaign_id, "user_input": "Enter the watchtower."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["applied_actions"] == []
    assert payload["tool_feedback"]["failed_calls"][0]["reason"] == "missing_required_item"


def test_watchtower_real_turn_entry_succeeds_after_legitimate_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_watchtower_campaign(client)

    for token in (
        "Move to village square.",
        "Move to old hut.",
        "Search the loose floorboard.",
        "Move to village square.",
        "Move to forest path.",
        "Move to watchtower entrance.",
    ):
        response = client.post(
            "/api/v1/chat/turn",
            json={"campaign_id": campaign_id, "user_input": token},
        )
        assert response.status_code == 200

    response = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": campaign_id, "user_input": "Enter the watchtower."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["applied_actions"][0]["tool"] == "move"
    assert payload["state_summary"]["active_area_id"] == "watchtower_inside"

    repo = FileRepo(tmp_path / "storage")
    campaign = repo.get_campaign(campaign_id)
    assert campaign.actors["pc_001"].position == "watchtower_inside"
    assert campaign.goal.status == "completed"
