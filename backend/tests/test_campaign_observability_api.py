from __future__ import annotations

import json
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


def _create_campaign(tmp_path: Path, campaign_id: str = "camp_0001") -> str:
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


def test_campaign_status_endpoint_returns_lifecycle_and_milestone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)

    response = client.get("/api/v1/campaign/status", params={"campaign_id": campaign_id})
    assert response.status_code == 200
    body = response.json()
    assert body["campaign_id"] == campaign_id
    assert body["ended"] is False
    assert body["milestone"]["current"] == "intro"


def test_advance_milestone_endpoint_updates_campaign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)

    response = client.post(
        "/api/v1/campaign/milestone/advance",
        json={"campaign_id": campaign_id, "summary": "manual checkpoint"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["campaign_id"] == campaign_id
    assert body["milestone"]["current"] == "milestone_1"
    assert body["milestone"]["summary"] == "manual checkpoint"


def test_campaign_status_endpoint_defaults_missing_lifecycle_for_legacy_campaign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)
    campaign_path = tmp_path / "storage" / "campaigns" / campaign_id / "campaign.json"
    payload = json.loads(campaign_path.read_text(encoding="utf-8"))
    payload.pop("lifecycle", None)
    campaign_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    response = client.get("/api/v1/campaign/status", params={"campaign_id": campaign_id})

    assert response.status_code == 200
    body = response.json()
    assert body["campaign_id"] == campaign_id
    assert body["ended"] is False
    assert body["reason"] is None
    assert body["ended_at"] is None
    assert body["milestone"]["current"] == "intro"
