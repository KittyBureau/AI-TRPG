from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

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


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    return TestClient(app)


def _create_campaign(
    tmp_path: Path,
    *,
    campaign_id: str,
    world_id: str,
) -> str:
    repo = FileRepo(tmp_path / "storage")
    campaign = Campaign(
        id=campaign_id,
        selected=Selected(
            world_id=world_id,
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


def test_get_campaign_world_lazy_creates_stub(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(
        tmp_path, campaign_id="camp_0001", world_id="world_001"
    )

    response = client.get(f"/api/v1/campaigns/{campaign_id}/world")
    assert response.status_code == 200
    body = response.json()
    assert body["world_id"] == "world_001"
    assert body["generator"]["id"] == "stub"

    world_path = tmp_path / "storage" / "worlds" / "world_001" / "world.json"
    assert world_path.exists()


def test_get_campaign_world_returns_409_when_world_id_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path, campaign_id="camp_0002", world_id="")

    response = client.get(f"/api/v1/campaigns/{campaign_id}/world")
    assert response.status_code == 409


def test_get_campaign_world_returns_404_when_campaign_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/v1/campaigns/camp_missing/world")
    assert response.status_code == 404
