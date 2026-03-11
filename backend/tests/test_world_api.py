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
from backend.domain.world_models import World, stable_world_timestamp
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


def test_list_worlds_returns_minimal_summaries_sorted_by_updated_at_desc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = FileRepo(tmp_path / "storage")
    repo.save_world(
        World(
            world_id="world_old",
            name="Older World",
            seed=1,
            generator={"id": "stub", "version": "1", "params": {}},
            schema_version="1",
            created_at="2026-03-03T00:00:00+00:00",
            updated_at="2026-03-03T00:00:00+00:00",
        )
    )
    repo.save_world(
        World(
            world_id="world_new",
            name="Newer World",
            seed=2,
            generator={"id": "alt", "version": "1", "params": {}},
            schema_version="1",
            created_at="2026-03-04T00:00:00+00:00",
            updated_at="2026-03-05T00:00:00+00:00",
        )
    )
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/v1/worlds/list")

    assert response.status_code == 200
    body = response.json()
    assert [item["world_id"] for item in body] == [
        "world_new",
        "test_watchtower_world",
        "world_old",
    ]
    assert body[0] == {
        "world_id": "world_new",
        "name": "Newer World",
        "generator": {"id": "alt"},
        "updated_at": "2026-03-05T00:00:00+00:00",
    }


def test_list_worlds_includes_watchtower_preset_without_storage_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/v1/worlds/list")

    assert response.status_code == 200
    body = response.json()
    watchtower = next(
        item for item in body if item["world_id"] == "test_watchtower_world"
    )
    assert watchtower == {
        "world_id": "test_watchtower_world",
        "name": "Test Watchtower World",
        "generator": {"id": "static_test_world"},
        "updated_at": stable_world_timestamp("test_watchtower_world"),
    }
    world_path = tmp_path / "storage" / "worlds" / "test_watchtower_world" / "world.json"
    assert not world_path.exists()


def test_list_worlds_skips_invalid_world_json_without_stub_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = FileRepo(tmp_path / "storage")
    repo.save_world(
        World(
            world_id="world_valid",
            name="Valid World",
            seed=7,
            generator={"id": "stub", "version": "1", "params": {}},
            schema_version="1",
            created_at="2026-03-04T00:00:00+00:00",
            updated_at="2026-03-04T00:00:00+00:00",
        )
    )
    invalid_path = tmp_path / "storage" / "worlds" / "world_bad" / "world.json"
    invalid_path.parent.mkdir(parents=True, exist_ok=True)
    invalid_path.write_text('{"world_id": ""}', encoding="utf-8")
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/v1/worlds/list")

    assert response.status_code == 200
    body = response.json()
    assert [item["world_id"] for item in body] == [
        "world_valid",
        "test_watchtower_world",
    ]
    assert not (tmp_path / "storage" / "worlds" / "world_missing").exists()


def test_generate_world_without_campaign_creates_resource_and_is_listed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/worlds/generate",
        json={"world_id": "world_api_new", "name": "API Generated World"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["world_id"] == "world_api_new"
    assert body["name"] == "API Generated World"
    assert body["created"] is True
    assert body["generator"]["id"] == "stub"

    list_response = client.get("/api/v1/worlds/list")
    assert list_response.status_code == 200
    listed_ids = [item["world_id"] for item in list_response.json()]
    assert "world_api_new" in listed_ids


def test_generate_world_repeat_reuses_existing_world_without_campaign_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    first = client.post(
        "/api/v1/worlds/generate",
        json={"world_id": "world_api_repeat", "name": "Initial Name"},
    )
    second = client.post(
        "/api/v1/worlds/generate",
        json={"world_id": "world_api_repeat"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert first_body["created"] is True
    assert second_body["created"] is False
    assert second_body["world_id"] == "world_api_repeat"
    assert second_body["name"] == "Initial Name"
    assert second_body["seed"] == first_body["seed"]
    world_path = tmp_path / "storage" / "worlds" / "world_api_repeat" / "world.json"
    assert world_path.exists()
    campaigns_root = tmp_path / "storage" / "campaigns"
    if campaigns_root.exists():
        assert list(campaigns_root.glob("camp_*")) == []


def test_generate_world_rejects_blank_world_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/v1/worlds/generate", json={"world_id": "   "})

    assert response.status_code == 400
    assert response.json()["detail"] == "world_id is required"


def test_generate_world_known_watchtower_preset_returns_static_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/worlds/generate",
        json={"world_id": "test_watchtower_world"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["world_id"] == "test_watchtower_world"
    assert body["name"] == "Test Watchtower World"
    assert body["start_area"] == "village_gate"
    assert body["objective"] == "Find the tower key in the old hut and enter the watchtower."
    assert body["generator"]["id"] == "static_test_world"
