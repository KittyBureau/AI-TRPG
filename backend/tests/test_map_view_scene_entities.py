from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.domain.models import (
    ActorState,
    Campaign,
    Entity,
    EntityLocation,
    Goal,
    MapArea,
    MapData,
    Milestone,
    Selected,
    SettingsSnapshot,
)
from backend.infra.file_repo import FileRepo


def _seed_campaign(tmp_path: Path, campaign_id: str) -> None:
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
        map=MapData(
            areas={
                "area_001": MapArea(id="area_001", name="Start", reachable_area_ids=["area_002"]),
                "area_002": MapArea(id="area_002", name="Side", reachable_area_ids=[]),
            },
            connections=[],
        ),
        actors={
            "pc_001": ActorState(position="area_001", hp=10, character_state="alive", meta={})
        },
        entities={
            "door_01": Entity(
                id="door_01",
                kind="object",
                label="Door",
                tags=["door"],
                loc=EntityLocation(type="area", id="area_001"),
                verbs=["inspect", "open"],
                state={},
                props={},
            ),
            "coin_01": Entity(
                id="coin_01",
                kind="item",
                label="Coin",
                tags=["loot"],
                loc=EntityLocation(type="area", id="area_002"),
                verbs=["inspect", "take"],
                state={},
                props={},
            ),
        },
    )
    repo.create_campaign(campaign)


def test_map_view_includes_entities_in_current_area(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign_id = "camp_map_scene"
    _seed_campaign(tmp_path, campaign_id)
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())

    response = client.get(
        "/api/v1/map/view",
        params={"campaign_id": campaign_id, "actor_id": "pc_001"},
    )
    assert response.status_code == 200
    payload = response.json()
    entities = payload["entities_in_area"]
    assert isinstance(entities, list)
    assert len(entities) == 1
    assert entities[0]["id"] == "door_01"
    assert entities[0]["verbs"] == ["inspect", "open"]
