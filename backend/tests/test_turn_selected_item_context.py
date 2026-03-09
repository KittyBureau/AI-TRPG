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
    Goal,
    MapArea,
    MapData,
    Milestone,
    Selected,
    SettingsSnapshot,
)
from backend.infra.file_repo import FileRepo


class _ContextCaptureLLM:
    last_system_prompt = ""

    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        _ContextCaptureLLM.last_system_prompt = system_prompt
        return {
            "assistant_text": "Selected item context checked.",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }


def _extract_prompt_context(system_prompt: str) -> Dict[str, Any]:
    marker = "Context: "
    if marker not in system_prompt:
        return {}
    return json.loads(system_prompt.rsplit(marker, 1)[1])


def _create_campaign(
    tmp_path: Path,
    campaign_id: str,
    *,
    trace_enabled: bool = False,
) -> None:
    repo = FileRepo(tmp_path / "storage")
    settings_snapshot = SettingsSnapshot()
    settings_snapshot.dialog.turn_profile_trace_enabled = trace_enabled
    campaign = Campaign(
        id=campaign_id,
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001", "pc_002"],
            active_actor_id="pc_001",
        ),
        settings_snapshot=settings_snapshot,
        goal=Goal(text="Use the right item.", status="active"),
        milestone=Milestone(current="intro", last_advanced_turn=0),
        map=MapData(
            areas={
                "area_001": MapArea(
                    id="area_001",
                    name="Start",
                    description="Start room.",
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
                inventory={"rusty_key": 1},
                meta={},
            ),
            "pc_002": ActorState(
                position="area_001",
                hp=10,
                character_state="alive",
                inventory={"torch": 2},
                meta={},
            ),
        },
    )
    repo.create_campaign(campaign)


def _write_item_catalog(tmp_path: Path, payload: object) -> None:
    catalog_path = tmp_path / "resources" / "data" / "items_catalog_v1.json"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        catalog_path.write_text(payload, encoding="utf-8")
        return
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(turn_service_module, "LLMClient", _ContextCaptureLLM)
    _ContextCaptureLLM.last_system_prompt = ""
    return TestClient(create_app())


def test_chat_turn_injects_selected_item_metadata_when_catalog_has_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_selected_item_valid", trace_enabled=True)
    _write_item_catalog(
        tmp_path,
        {
            "rusty_key": {
                "name": "rusty key",
                "description": "an old iron key, possibly opens ancient locks",
            }
        },
    )
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": "camp_selected_item_valid",
            "user_input": "Use the key.",
            "execution": {"actor_id": "pc_001"},
            "context_hints": {"selected_item_id": "rusty_key"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["effective_actor_id"] == "pc_001"
    assert payload["debug"]["selected_item"] == {
        "id": "rusty_key",
        "has_metadata": True,
    }
    context = _extract_prompt_context(_ContextCaptureLLM.last_system_prompt)
    assert context["selected_item"] == {
        "id": "rusty_key",
        "name": "rusty key",
        "description": "an old iron key, possibly opens ancient locks",
        "quantity": 1,
    }


def test_chat_turn_falls_back_to_phase_b_shape_when_catalog_has_no_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_selected_item_missing", trace_enabled=True)
    _write_item_catalog(
        tmp_path,
        {
            "torch": {
                "name": "torch",
                "description": "a simple handheld torch for lighting dark areas",
            }
        },
    )
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": "camp_selected_item_missing",
            "user_input": "Try using the key.",
            "execution": {"actor_id": "pc_001"},
            "context_hints": {"selected_item_id": "rusty_key"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["narrative_text"] == "Selected item context checked."
    assert payload["debug"]["selected_item"] == {
        "id": "rusty_key",
        "has_metadata": False,
    }
    context = _extract_prompt_context(_ContextCaptureLLM.last_system_prompt)
    assert context["selected_item"] == {"id": "rusty_key", "quantity": 1}


def test_chat_turn_falls_back_to_phase_b_shape_when_catalog_is_invalid_and_trace_stays_gated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_selected_item_invalid_catalog")
    _write_item_catalog(tmp_path, "{not-json")
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": "camp_selected_item_invalid_catalog",
            "user_input": "Use the key.",
            "execution": {"actor_id": "pc_001"},
            "context_hints": {"selected_item_id": "rusty_key"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["effective_actor_id"] == "pc_001"
    assert "debug" not in payload
    context = _extract_prompt_context(_ContextCaptureLLM.last_system_prompt)
    assert context["selected_item"] == {"id": "rusty_key", "quantity": 1}


def test_chat_turn_omits_selected_item_debug_when_trace_is_on_but_hint_is_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_selected_item_absent", trace_enabled=True)
    _write_item_catalog(
        tmp_path,
        {
            "rusty_key": {
                "name": "rusty key",
                "description": "an old iron key, possibly opens ancient locks",
            }
        },
    )
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": "camp_selected_item_absent",
            "user_input": "Open the door.",
            "execution": {"actor_id": "pc_001"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "debug" in payload
    assert "selected_item" not in payload["debug"]
    context = _extract_prompt_context(_ContextCaptureLLM.last_system_prompt)
    assert "selected_item" not in context


def test_chat_turn_still_ignores_invalid_selected_item_even_when_catalog_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_selected_item_invalid_hint", trace_enabled=True)
    _write_item_catalog(
        tmp_path,
        {
            "torch": {
                "name": "torch",
                "description": "a simple handheld torch for lighting dark areas",
            }
        },
    )
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": "camp_selected_item_invalid_hint",
            "user_input": "Use the torch.",
            "execution": {"actor_id": "pc_001"},
            "context_hints": {"selected_item_id": "torch"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["effective_actor_id"] == "pc_001"
    assert payload["narrative_text"] == "Selected item context checked."
    assert "debug" in payload
    assert "selected_item" not in payload["debug"]
    context = _extract_prompt_context(_ContextCaptureLLM.last_system_prompt)
    assert "selected_item" not in context
