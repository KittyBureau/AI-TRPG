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
    Milestone,
    Selected,
    SettingsSnapshot,
)
from backend.infra.file_repo import FileRepo


class _StubLLM:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self.payload = payload

    def generate(self, system_prompt: str, user_input: str, debug_append: Any) -> Dict[str, Any]:
        return dict(self.payload)


def _create_campaign(tmp_path: Path, campaign_id: str, *, strict: bool) -> None:
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
        actors={
            "pc_001": ActorState(
                position="area_001",
                hp=10,
                character_state="alive",
                meta={},
            )
        },
    )
    campaign.settings_snapshot.dialog.strict_semantic_guard = strict
    repo.create_campaign(campaign)


def test_default_guard_keeps_fallback_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        turn_service_module,
        "LLMClient",
        lambda: _StubLLM(
            {
                "assistant_text": "Fallback allowed.",
                "dialog_type": "bad_type",
                "tool_calls": [],
            }
        ),
    )
    _create_campaign(tmp_path, "camp_0001", strict=False)
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": "camp_0001", "user_input": "hello"},
    )
    assert response.status_code == 200
    assert response.json()["dialog_type"] == "scene_description"


def test_strict_guard_rejects_invalid_dialog_type_with_422(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        turn_service_module,
        "LLMClient",
        lambda: _StubLLM(
            {
                "assistant_text": "Should fail.",
                "dialog_type": "bad_type",
                "tool_calls": [],
            }
        ),
    )
    _create_campaign(tmp_path, "camp_0002", strict=True)
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": "camp_0002", "user_input": "hello"},
    )
    assert response.status_code == 422
