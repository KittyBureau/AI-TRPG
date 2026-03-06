from __future__ import annotations

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


class _StubLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        return {
            "assistant_text": "Trace test response.",
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
        goal=Goal(text="Trace goal", status="active"),
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
                inventory={},
                meta={},
            )
        },
    )
    repo.create_campaign(campaign)


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(turn_service_module, "LLMClient", _StubLLM)
    return TestClient(create_app())


def test_chat_turn_omits_top_level_debug_when_trace_is_off(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_trace_off")
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": "camp_trace_off", "user_input": "hello"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "debug" not in payload
    assert payload["narrative_text"] == "Trace test response."


def test_settings_apply_toggles_trace_and_chat_turn_debug_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_trace_toggle")
    client = _client(tmp_path, monkeypatch)

    apply_on = client.post(
        "/api/v1/settings/apply",
        json={
            "campaign_id": "camp_trace_toggle",
            "patch": {"dialog.turn_profile_trace_enabled": True},
        },
    )
    assert apply_on.status_code == 200
    assert apply_on.json()["snapshot"]["dialog"]["turn_profile_trace_enabled"] is True
    assert "dialog.turn_profile_trace_enabled" in apply_on.json()["change_summary"]

    traced_turn = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": "camp_trace_toggle", "user_input": "hello"},
    )
    assert traced_turn.status_code == 200
    traced_payload = traced_turn.json()
    assert "debug" in traced_payload
    debug = traced_payload["debug"]
    assert isinstance(debug, dict)
    assert isinstance(debug.get("resources"), dict)
    for key in (
        "prompts",
        "flows",
        "schemas",
        "templates",
        "policies",
        "template_usage",
    ):
        assert key in debug["resources"]
        assert isinstance(debug["resources"][key], list)
    assert isinstance(debug.get("prompt"), dict)
    assert isinstance(debug.get("flow"), dict)
    assert isinstance(debug.get("schemas"), list)
    assert isinstance(debug.get("templates"), list)
    assert "used_profile_hash" in debug

    apply_off = client.post(
        "/api/v1/settings/apply",
        json={
            "campaign_id": "camp_trace_toggle",
            "patch": {"dialog.turn_profile_trace_enabled": False},
        },
    )
    assert apply_off.status_code == 200
    assert apply_off.json()["snapshot"]["dialog"]["turn_profile_trace_enabled"] is False

    untraced_turn = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": "camp_trace_toggle", "user_input": "hello again"},
    )
    assert untraced_turn.status_code == 200
    assert "debug" not in untraced_turn.json()
