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


class _StubNoopLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        return {
            "assistant_text": "No-op turn.",
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
        goal=Goal(text="Stay alive.", status="active"),
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


def test_chat_turn_returns_409_when_campaign_turn_is_busy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _create_campaign(tmp_path, "camp_lock_busy")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(turn_service_module, "LLMClient", _StubNoopLLM)

    lock = turn_service_module._CAMPAIGN_TURN_LOCKS.try_acquire("camp_lock_busy")
    assert lock is not None
    try:
        client = TestClient(create_app())
        response = client.post(
            "/api/v1/chat/turn",
            json={"campaign_id": "camp_lock_busy", "user_input": "hello"},
        )
        assert response.status_code == 409
        assert "already running" in response.json()["detail"]
    finally:
        turn_service_module._CAMPAIGN_TURN_LOCKS.release(lock)

