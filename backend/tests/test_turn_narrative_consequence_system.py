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
from backend.infra.file_repo import FileRepo


def _extract_prompt_context(system_prompt: str) -> Dict[str, Any]:
    marker = "Context: "
    if marker not in system_prompt:
        return {}
    return json.loads(system_prompt.rsplit(marker, 1)[1])


class _ConsequenceAwareLLM:
    last_system_prompt = ""

    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        _ConsequenceAwareLLM.last_system_prompt = system_prompt
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
        if token == "Look around carefully.":
            context = _extract_prompt_context(system_prompt)
            consequences = context.get("consequences", {})
            items = consequences.get("items", []) if isinstance(consequences, dict) else []
            assistant_text = "The air feels steady."
            if isinstance(items, list) and items:
                first = items[0]
                if isinstance(first, dict):
                    hint = first.get("narrative_hint")
                    if isinstance(hint, str) and hint.strip():
                        assistant_text = hint.strip()
            return {
                "assistant_text": assistant_text,
                "dialog_type": "scene_description",
                "tool_calls": [],
            }
        return {
            "assistant_text": "The scene stays quiet.",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(turn_service_module, "LLMClient", _ConsequenceAwareLLM)
    _ConsequenceAwareLLM.last_system_prompt = ""
    return TestClient(create_app())


def _repo(tmp_path: Path) -> FileRepo:
    return FileRepo(tmp_path / "storage")


def _create_watchtower_campaign(client: TestClient) -> str:
    response = client.post(
        "/api/v1/campaign/create",
        json={"world_id": "test_watchtower_world"},
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


def test_successful_turn_does_not_raise_consequence_state(
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
    assert payload["state_summary"]["consequences"] == {
        "level": 0,
        "active_count": 0,
        "last_turn_index": 0,
        "types": [],
        "tones": [],
    }
    campaign = _repo(tmp_path).get_campaign(campaign_id)
    assert campaign.consequences.entries == {}
    assert campaign.facts == {}


def test_repeated_wrong_item_triggers_area_pressure_consequence(
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
    assert payload["tool_feedback"]["failed_calls"] == [
        {
            "id": "call_move_inside",
            "tool": "move",
            "status": "error",
            "reason": "missing_required_item",
        }
    ]
    assert payload["state_summary"]["mistakes"]["categories"] == ["wrong_item"]
    assert payload["state_summary"]["consequences"] == {
        "level": 1,
        "active_count": 1,
        "last_turn_index": 5,
        "types": ["area_pressure"],
        "tones": ["watchful"],
    }
    assert "locked" in payload["narrative_text"].lower()
    assert "watchful now" in payload["narrative_text"].lower()

    debug_consequences = payload["debug"]["consequences"]
    assert len(debug_consequences["triggered_consequence_ids"]) == 1
    assert debug_consequences["removed_consequence_ids"] == []
    assert len(debug_consequences["source_signal_ids"]) == 1
    assert len(debug_consequences["entries"]) == 1
    consequence_entry = debug_consequences["entries"][0]
    assert consequence_entry["type"] == "area_pressure"
    assert consequence_entry["scope_kind"] == "area"
    assert consequence_entry["area_id"] == "watchtower_entrance"
    assert consequence_entry["target_id"] == "watchtower_inside"
    assert consequence_entry["tone"] == "watchful"
    assert consequence_entry["source_categories"] == ["wrong_item"]

    campaign = _repo(tmp_path).get_campaign(campaign_id)
    assert campaign.facts == {}
    assert len(campaign.consequences.entries) == 1
    stored = next(iter(campaign.consequences.entries.values()))
    assert stored.type == "area_pressure"
    assert stored.level == 1
    assert stored.area_id == "watchtower_entrance"
    assert stored.target_id == "watchtower_inside"
    assert stored.tone == "watchful"
    assert stored.source_categories == ["wrong_item"]


def test_consequence_is_visible_on_later_turn_without_false_escalation(
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

    for _ in range(2):
        response = client.post(
            "/api/v1/chat/turn",
            json={"campaign_id": campaign_id, "user_input": "Enter the watchtower."},
        )
        assert response.status_code == 200

    look = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": campaign_id, "user_input": "Look around carefully."},
    )

    assert look.status_code == 200
    payload = look.json()
    assert "watchful now" in payload["narrative_text"].lower()
    assert payload["tool_feedback"] is None
    assert payload["state_summary"]["consequences"] == {
        "level": 1,
        "active_count": 1,
        "last_turn_index": 5,
        "types": ["area_pressure"],
        "tones": ["watchful"],
    }

    context = _extract_prompt_context(_ConsequenceAwareLLM.last_system_prompt)
    consequence_context = context["consequences"]
    assert consequence_context["slot"] == "narrative_consequence_v1"
    assert consequence_context["overall_level"] == 1
    assert consequence_context["active_count"] == 1
    assert len(consequence_context["items"]) == 1
    consequence_item = consequence_context["items"][0]
    assert consequence_item["type"] == "area_pressure"
    assert consequence_item["tone"] == "watchful"
    assert consequence_item["area_id"] == "watchtower_entrance"
    assert consequence_item["target_id"] == "watchtower_inside"
    assert consequence_item["source_categories"] == ["wrong_item"]

    campaign = _repo(tmp_path).get_campaign(campaign_id)
    assert campaign.facts == {}
    assert campaign.consequences.last_turn_index == 5
    assert len(campaign.consequences.entries) == 1
