from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import backend.app.turn_service as turn_service_module
from backend.api.main import create_app
from backend.app.item_runtime import grant_item_to_actor
from backend.app.world_presets import MIDNIGHT_ARCHIVE_WORLD_ID
from backend.infra.file_repo import FileRepo


def _extract_prompt_context(system_prompt: str) -> Dict[str, Any]:
    marker = "Context: "
    if marker not in system_prompt:
        return {}
    return json.loads(system_prompt.rsplit(marker, 1)[1])


class _RuleAwareAlignmentLLM:
    last_system_prompt = ""

    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        _RuleAwareAlignmentLLM.last_system_prompt = system_prompt
        context = _extract_prompt_context(system_prompt)
        movement_rules = context.get("movement_rules", {})

        if user_input == "How do I get into the Restricted Archive?":
            blocked_archive = next(
                (
                    item
                    for item in movement_rules.get("blocked_transitions", [])
                    if isinstance(item, dict)
                    and item.get("to_area_id") == "restricted_archive"
                ),
                {},
            )
            required_label = blocked_archive.get("requires_label", "the right item")
            return {
                "assistant_text": (
                    "The Restricted Archive is connected, but locked. "
                    f"You may need {required_label}."
                ),
                "dialog_type": "scene_description",
                "tool_calls": [],
            }

        if user_input == "Enter the Restricted Archive now.":
            return {
                "assistant_text": "You step into the Restricted Archive.",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_move_archive",
                        "tool": "move",
                        "args": {
                            "actor_id": "pc_001",
                            "to_area_id": "restricted_archive",
                        },
                    }
                ],
            }

        if user_input == "Take the pass from the tray.":
            return {
                "assistant_text": "You grab the pass from the tray.",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_take_tray",
                        "tool": "scene_action",
                        "args": {
                            "actor_id": "pc_001",
                            "action": "take",
                            "target_id": "lost_and_found_tray",
                            "params": {},
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
    monkeypatch.setattr(turn_service_module, "LLMClient", _RuleAwareAlignmentLLM)
    _RuleAwareAlignmentLLM.last_system_prompt = ""
    return TestClient(create_app())


def _create_midnight_archive_campaign(client: TestClient) -> str:
    response = client.post(
        "/api/v1/campaign/create",
        json={"world_id": MIDNIGHT_ARCHIVE_WORLD_ID},
    )
    assert response.status_code == 200
    campaign_id = response.json()["campaign_id"]
    assert isinstance(campaign_id, str) and campaign_id
    return campaign_id


def _set_actor_position(
    tmp_path: Path,
    campaign_id: str,
    *,
    area_id: str,
) -> None:
    repo = FileRepo(tmp_path / "storage")
    campaign = repo.get_campaign(campaign_id)
    campaign.actors["pc_001"].position = area_id
    repo.save_campaign(campaign)


def _grant_inventory_item(
    tmp_path: Path,
    campaign_id: str,
    *,
    item_id: str,
    label: str,
) -> None:
    repo = FileRepo(tmp_path / "storage")
    campaign = repo.get_campaign(campaign_id)
    grant_item_to_actor(
        campaign,
        actor_id="pc_001",
        definition_id=item_id,
        quantity=1,
        label=label,
        stack_id_salt=f"{campaign_id}:{item_id}",
    )
    repo.save_campaign(campaign)


def test_rule_aware_question_mentions_blocked_archive_requirement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_midnight_archive_campaign(client)
    _set_actor_position(tmp_path, campaign_id, area_id="storage_room")

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": campaign_id,
            "user_input": "How do I get into the Restricted Archive?",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "locked" in payload["narrative_text"].lower()
    assert "archive key" in payload["narrative_text"].lower()
    assert "freely" not in payload["narrative_text"].lower()

    context = _extract_prompt_context(_RuleAwareAlignmentLLM.last_system_prompt)
    assert context["movement_rules"]["reachable_areas"] == [
        {"to_area_id": "clerk_office", "name": "Clerk Office"},
        {"to_area_id": "returns_annex", "name": "Returns Annex"},
    ]
    assert context["movement_rules"]["blocked_transitions"] == [
        {
            "to_area_id": "restricted_archive",
            "name": "Restricted Archive",
            "reason": "locked",
            "requires_item_id": "archive_key",
            "requires_label": "Archive Key",
        }
    ]


def test_blocked_move_reports_why_it_fails_instead_of_missing_required_item(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_midnight_archive_campaign(client)
    _set_actor_position(tmp_path, campaign_id, area_id="storage_room")

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": campaign_id,
            "user_input": "Enter the Restricted Archive now.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["applied_actions"] == []
    assert payload["tool_feedback"]["failed_calls"][0]["reason"] == "missing_required_item"
    assert "locked" in payload["narrative_text"].lower()
    assert "archive key" in payload["narrative_text"].lower()
    assert "missing_required_item" not in payload["narrative_text"].lower()
    assert "step into the restricted archive" not in payload["narrative_text"].lower()


def test_take_before_search_explains_search_then_take_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_midnight_archive_campaign(client)
    _set_actor_position(tmp_path, campaign_id, area_id="lobby")

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": campaign_id,
            "user_input": "Take the pass from the tray.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["applied_actions"][0]["tool"] == "scene_action"
    assert payload["applied_actions"][0]["result"]["ok"] is False
    assert "search it first" in payload["narrative_text"].lower()
    assert "tray" in payload["narrative_text"].lower()


def test_wrong_item_gate_feedback_names_mismatch_and_required_item(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_midnight_archive_campaign(client)
    _set_actor_position(tmp_path, campaign_id, area_id="storage_room")
    _grant_inventory_item(
        tmp_path,
        campaign_id,
        item_id="office_pass",
        label="Office Pass",
    )

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": campaign_id,
            "user_input": "Enter the Restricted Archive now.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["applied_actions"] == []
    assert "office pass does not work here" in payload["narrative_text"].lower()
    assert "archive key" in payload["narrative_text"].lower()
