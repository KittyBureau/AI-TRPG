from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.domain.models import ActorState, Campaign, Goal, Milestone, Selected, SettingsSnapshot
from backend.infra.file_repo import FileRepo


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    return TestClient(app)


def _create_campaign(
    tmp_path: Path,
    *,
    campaign_id: str = "camp_0001",
    active_actor_id: str = "pc_001",
) -> str:
    repo = FileRepo(tmp_path / "storage")
    campaign = Campaign(
        id=campaign_id,
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001"],
            active_actor_id=active_actor_id,
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


def test_character_library_create_list_get_and_skip_invalid_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)

    create_resp = client.post(
        "/api/v1/characters/library",
        json={
            "name": "Rin",
            "summary": "A quiet scout.",
            "tags": ["scout", "calm"],
            "meta": {"origin": "manual"},
            "extra_note": "kept",
        },
    )
    assert create_resp.status_code == 200
    create_body = create_resp.json()
    character_id = create_body["character_id"]
    assert create_body["ok"] is True
    assert create_body["fact"]["id"] == character_id
    assert create_body["fact"]["extra_note"] == "kept"

    library_dir = tmp_path / "storage" / "characters_library"
    bad_path = library_dir / "broken.json"
    bad_path.write_text("{invalid", encoding="utf-8")

    list_resp = client.get("/api/v1/characters/library")
    assert list_resp.status_code == 200
    listed = list_resp.json()
    assert any(item["id"] == character_id for item in listed)
    assert not any(item["id"] == "broken" for item in listed)

    get_resp = client.get(f"/api/v1/characters/library/{character_id}")
    assert get_resp.status_code == 200
    get_body = get_resp.json()
    assert get_body["id"] == character_id
    assert get_body["name"] == "Rin"
    assert get_body["summary"] == "A quiet scout."
    assert get_body["meta"]["origin"] == "manual"


def test_party_load_adds_actor_and_party_keeps_non_empty_active_actor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path, active_actor_id="pc_001")

    create_resp = client.post(
        "/api/v1/characters/library",
        json={"id": "ch_hero001", "name": "Hero One", "summary": "Frontliner"},
    )
    assert create_resp.status_code == 200

    load_resp = client.post(
        f"/api/v1/campaigns/{campaign_id}/party/load",
        json={"character_id": "ch_hero001"},
    )
    assert load_resp.status_code == 200
    load_body = load_resp.json()
    assert load_body["ok"] is True
    assert "ch_hero001" in load_body["party_character_ids"]
    assert load_body["active_actor_id"] == "pc_001"

    repo = FileRepo(tmp_path / "storage")
    campaign = repo.get_campaign(campaign_id)
    assert "ch_hero001" in campaign.actors
    assert "ch_hero001" in campaign.selected.party_character_ids
    assert campaign.selected.active_actor_id == "pc_001"
    actor_meta = campaign.actors["ch_hero001"].meta
    assert actor_meta["character_id"] == "ch_hero001"
    assert actor_meta["profile"]["name"] == "Hero One"


def test_party_load_sets_active_actor_only_when_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path, campaign_id="camp_0002", active_actor_id="")

    create_resp = client.post(
        "/api/v1/characters/library",
        json={"id": "ch_hero002", "name": "Hero Two"},
    )
    assert create_resp.status_code == 200

    load_resp = client.post(
        f"/api/v1/campaigns/{campaign_id}/party/load",
        json={"character_id": "ch_hero002", "set_active_if_empty": True},
    )
    assert load_resp.status_code == 200
    assert load_resp.json()["active_actor_id"] == "ch_hero002"

    repo = FileRepo(tmp_path / "storage")
    campaign = repo.get_campaign(campaign_id)
    assert campaign.selected.active_actor_id == "ch_hero002"
    profile = campaign.actors["ch_hero002"].meta.get("profile")
    assert isinstance(profile, dict)
    assert profile["id"] == "ch_hero002"
