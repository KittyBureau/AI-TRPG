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


class _GuidanceLayerLLM:
    last_system_prompt = ""

    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        _GuidanceLayerLLM.last_system_prompt = system_prompt
        context = _extract_prompt_context(system_prompt)
        guidance = context.get("guidance", {})

        if user_input == "How do I get into the Restricted Archive?":
            blocked_hint = next(
                (
                    item
                    for item in guidance.get("blocked_transition_hints", [])
                    if isinstance(item, dict)
                    and item.get("to_area_id") == "restricted_archive"
                ),
                {},
            )
            required_label = blocked_hint.get("requires_label", "the right item")
            suggestions = blocked_hint.get("suggestions", [])
            lead = ""
            if isinstance(suggestions, list):
                for suggestion in suggestions:
                    if not isinstance(suggestion, dict):
                        continue
                    text = suggestion.get("text")
                    if isinstance(text, str) and text.strip():
                        lead = text.strip()
                        break
            assistant_text = (
                f"The Restricted Archive is locked. You may need {required_label}."
            )
            if lead:
                assistant_text = f"{assistant_text} {lead}"
            return {
                "assistant_text": assistant_text,
                "dialog_type": "scene_description",
                "tool_calls": [],
            }

        if user_input == "What should I do now?":
            suggestions = guidance.get("idle_suggestions", [])
            texts: list[str] = []
            if isinstance(suggestions, list):
                for suggestion in suggestions:
                    if not isinstance(suggestion, dict):
                        continue
                    text = suggestion.get("text")
                    if isinstance(text, str) and text.strip():
                        texts.append(text.strip())
                    if len(texts) >= 2:
                        break
            assistant_text = " ".join(texts) if texts else "Think through the scene."
            return {
                "assistant_text": assistant_text,
                "dialog_type": "scene_description",
                "tool_calls": [],
            }

        if user_input == "Enter the Restricted Archive now.":
            return {
                "assistant_text": "",
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

        return {
            "assistant_text": "The scene stays quiet.",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(turn_service_module, "LLMClient", _GuidanceLayerLLM)
    _GuidanceLayerLLM.last_system_prompt = ""
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


def test_guidance_question_uses_runtime_block_hint_and_source_suggestion(
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
    assert "clerk office" in payload["narrative_text"].lower()

    context = _extract_prompt_context(_GuidanceLayerLLM.last_system_prompt)
    guidance = context["guidance"]
    assert guidance["hint_level"] == 1
    assert guidance["blocked_transition_hints"] == [
        {
            "to_area_id": "restricted_archive",
            "name": "Restricted Archive",
            "requires_label": "Archive Key",
            "suggestions": [
                {
                    "kind": "source",
                    "text": "Clerk Office might be worth checking.",
                }
            ],
        }
    ]


def test_blocked_move_hint_strength_scales_after_repeated_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_midnight_archive_campaign(client)
    _set_actor_position(tmp_path, campaign_id, area_id="storage_room")

    first = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": campaign_id,
            "user_input": "Enter the Restricted Archive now.",
        },
    )
    second = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": campaign_id,
            "user_input": "Enter the Restricted Archive now.",
        },
    )
    third = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": campaign_id,
            "user_input": "Enter the Restricted Archive now.",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 200

    first_text = first.json()["narrative_text"].lower()
    second_text = second.json()["narrative_text"].lower()
    third_text = third.json()["narrative_text"].lower()

    assert "clerk office might be worth checking" in first_text
    assert "desk safe in clerk office may be a useful lead" in second_text
    assert "desk safe in clerk office might be worth a closer look" in third_text
    assert "you should" not in third_text
    assert "search desk safe" not in third_text


def test_wrong_item_guidance_names_item_mismatch_and_likely_usage(
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
    narrative_text = response.json()["narrative_text"].lower()
    assert "office pass does not work here" in narrative_text
    assert "office pass may be more relevant around clerk office" in narrative_text
    assert "archive key" in narrative_text
    assert "used to access clerk office" not in narrative_text


def test_idle_guidance_returns_at_most_two_contextual_next_steps(
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
            "user_input": "What should I do now?",
        },
    )

    assert response.status_code == 200
    narrative_text = response.json()["narrative_text"].lower()
    assert "clerk office" in narrative_text
    assert ("janitor" in narrative_text) or ("archive door" in narrative_text)
    assert "you should" not in narrative_text

    context = _extract_prompt_context(_GuidanceLayerLLM.last_system_prompt)
    idle_suggestions = context["guidance"]["idle_suggestions"]
    assert 1 <= len(idle_suggestions) <= 2
