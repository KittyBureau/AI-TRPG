from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import backend.app.turn_service as turn_service_module
from backend.api.main import create_app
from backend.app.item_runtime import create_runtime_item_stack
from backend.app.world_presets import (
    TEST_WATCHTOWER_GATE_ITEM_ID,
    TEST_WATCHTOWER_WORLD_ID,
)
from backend.infra.file_repo import FileRepo

_ZERO_MISTAKE_SUMMARY = {
    "level": 0,
    "total_count": 0,
    "last_turn_index": 0,
    "entry_count": 0,
    "categories": [],
}


class _RecoverableFailureLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        token = user_input.strip()
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
                        "args": {
                            "actor_id": "pc_001",
                            "to_area_id": "watchtower_entrance",
                        },
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
                        "args": {
                            "actor_id": "pc_001",
                            "to_area_id": "watchtower_inside",
                        },
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
    monkeypatch.setattr(turn_service_module, "LLMClient", _RecoverableFailureLLM)
    return TestClient(create_app())


def _repo(tmp_path: Path) -> FileRepo:
    return FileRepo(tmp_path / "storage")


def _create_watchtower_campaign(client: TestClient) -> str:
    response = client.post(
        "/api/v1/campaign/create",
        json={"world_id": TEST_WATCHTOWER_WORLD_ID},
    )
    assert response.status_code == 200
    campaign_id = response.json()["campaign_id"]
    assert isinstance(campaign_id, str) and campaign_id
    return campaign_id


def _set_trace_enabled(tmp_path: Path, campaign_id: str, enabled: bool = True) -> None:
    repo = _repo(tmp_path)
    campaign = repo.get_campaign(campaign_id)
    campaign.settings_snapshot.dialog.turn_profile_trace_enabled = enabled
    repo.save_campaign(campaign)


def _grant_actor_item(
    tmp_path: Path,
    campaign_id: str,
    *,
    item_id: str,
    label: str,
) -> None:
    repo = _repo(tmp_path)
    campaign = repo.get_campaign(campaign_id)
    stack = create_runtime_item_stack(
        definition_id=item_id,
        quantity=1,
        parent_type="actor",
        parent_id="pc_001",
        label=label,
    )
    campaign.items[stack.stack_id] = stack
    repo.save_campaign(campaign)


def _move_to_watchtower_entrance(client: TestClient, campaign_id: str) -> None:
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


def test_successful_turn_does_not_write_mistake_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_watchtower_campaign(client)

    response = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": campaign_id, "user_input": "Move to village square."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_feedback"] is None
    assert payload["state_summary"]["mistakes"] == _ZERO_MISTAKE_SUMMARY

    campaign = _repo(tmp_path).get_campaign(campaign_id)
    assert campaign.mistakes.total_count == 0
    assert campaign.mistakes.level == 0
    assert campaign.mistakes.entries == {}


def test_wrong_item_failure_records_mistake_signal_and_keeps_facts_clean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_watchtower_campaign(client)
    _set_trace_enabled(tmp_path, campaign_id)
    _move_to_watchtower_entrance(client, campaign_id)
    _grant_actor_item(
        tmp_path,
        campaign_id,
        item_id="office_pass",
        label="Office Pass",
    )

    response = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": campaign_id, "user_input": "Enter the watchtower."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["applied_actions"] == []
    assert payload["tool_feedback"]["failed_calls"] == [
        {
            "id": "call_move_inside",
            "tool": "move",
            "status": "error",
            "reason": "missing_required_item",
        }
    ]
    assert payload["state_summary"]["mistakes"] == {
        "level": 1,
        "total_count": 1,
        "last_turn_index": 4,
        "entry_count": 1,
        "categories": ["wrong_item"],
    }
    debug_mistakes = payload["debug"]["mistakes"]
    assert debug_mistakes["recorded_signal_ids"]
    assert debug_mistakes["pruned_signal_ids"] == []
    assert len(debug_mistakes["recorded_signals"]) == 1
    recorded = debug_mistakes["recorded_signals"][0]
    assert recorded["category"] == "wrong_item"
    assert recorded["source_tool"] == "move"
    assert recorded["target_id"] == "watchtower_inside"
    assert recorded["item_id"] == "office_pass"
    assert recorded["required_item_id"] == TEST_WATCHTOWER_GATE_ITEM_ID
    assert recorded["count"] == 1
    assert recorded["level"] == 1

    campaign = _repo(tmp_path).get_campaign(campaign_id)
    assert campaign.facts == {}
    assert campaign.mistakes.total_count == 1
    assert campaign.mistakes.level == 1
    assert len(campaign.mistakes.entries) == 1
    entry = next(iter(campaign.mistakes.entries.values()))
    assert entry.category == "wrong_item"
    assert entry.item_id == "office_pass"
    assert entry.required_item_id == TEST_WATCHTOWER_GATE_ITEM_ID
    assert entry.count == 1
    assert entry.level == 1


def test_repeated_wrong_item_failure_increments_existing_mistake_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_watchtower_campaign(client)
    _set_trace_enabled(tmp_path, campaign_id)
    _move_to_watchtower_entrance(client, campaign_id)
    _grant_actor_item(
        tmp_path,
        campaign_id,
        item_id="office_pass",
        label="Office Pass",
    )

    first = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": campaign_id, "user_input": "Enter the watchtower."},
    )
    second = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": campaign_id, "user_input": "Enter the watchtower."},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    payload = second.json()
    assert payload["state_summary"]["mistakes"] == {
        "level": 2,
        "total_count": 2,
        "last_turn_index": 5,
        "entry_count": 1,
        "categories": ["wrong_item"],
    }
    recorded = payload["debug"]["mistakes"]["recorded_signals"][0]
    assert recorded["category"] == "wrong_item"
    assert recorded["count"] == 2
    assert recorded["level"] == 2
    assert recorded["last_turn_index"] == 5

    campaign = _repo(tmp_path).get_campaign(campaign_id)
    assert campaign.mistakes.total_count == 2
    assert campaign.mistakes.level == 2
    assert len(campaign.mistakes.entries) == 1
    entry = next(iter(campaign.mistakes.entries.values()))
    assert entry.count == 2
    assert entry.level == 2
    assert entry.last_turn_index == 5
