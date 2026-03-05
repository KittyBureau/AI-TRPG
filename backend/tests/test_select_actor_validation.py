from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.domain.models import ActorState, Campaign, Goal, Milestone, Selected, SettingsSnapshot
from backend.infra.file_repo import FileRepo


class _DummyLLMClient:
    def __init__(self, *args, **kwargs) -> None:
        pass


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("backend.app.turn_service.LLMClient", _DummyLLMClient)
    monkeypatch.chdir(tmp_path)
    app = create_app()
    return TestClient(app)


def _create_campaign(tmp_path: Path, campaign_id: str = "camp_select_001") -> str:
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
    repo.create_campaign(campaign)
    return campaign_id


def test_select_actor_rejects_actor_not_in_party(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)

    before_resp = client.get("/api/v1/campaign/get", params={"campaign_id": campaign_id})
    assert before_resp.status_code == 200
    before_active = before_resp.json()["selected"]["active_actor_id"]
    assert before_active

    select_resp = client.post(
        "/api/v1/campaign/select_actor",
        json={"campaign_id": campaign_id, "active_actor_id": "pc_missing"},
    )
    assert select_resp.status_code == 400
    assert "party_character_ids" in select_resp.text

    after_resp = client.get("/api/v1/campaign/get", params={"campaign_id": campaign_id})
    assert after_resp.status_code == 200
    assert after_resp.json()["selected"]["active_actor_id"] == before_active
