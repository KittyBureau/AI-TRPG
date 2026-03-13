from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.app.item_runtime import create_runtime_item_stack
from backend.domain.models import (
    ActorState,
    Campaign,
    Goal,
    MapArea,
    Milestone,
    Selected,
    SettingsSnapshot,
)
from backend.infra.file_repo import FileRepo


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    return TestClient(app)


def _create_campaign(tmp_path: Path, campaign_id: str = "camp_0001") -> tuple[str, str]:
    repo = FileRepo(tmp_path / "storage")
    torch_stack = create_runtime_item_stack(
        definition_id="torch",
        quantity=1,
        parent_type="actor",
        parent_id="pc_001",
        label="torch",
        stack_id_salt="test_campaign_get_api:pc_001:torch",
    )
    campaign = Campaign(
        id=campaign_id,
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001", "pc_002"],
            active_actor_id="pc_002",
        ),
        settings_snapshot=SettingsSnapshot(),
        goal=Goal(text="Goal", status="active"),
        milestone=Milestone(current="intro", last_advanced_turn=0),
        actors={
            "pc_001": ActorState(
                position="area_001",
                hp=10,
                character_state="alive",
                inventory={},
                meta={},
            ),
            "pc_002": ActorState(
                position="area_002",
                hp=10,
                character_state="alive",
                inventory={},
                meta={},
            ),
        },
        items={torch_stack.stack_id: torch_stack},
        map={
            "areas": {
                "area_001": MapArea(
                    id="area_001",
                    name="Camp",
                    description="Initial camp",
                    reachable_area_ids=["area_002"],
                ),
                "area_002": MapArea(
                    id="area_002",
                    name="Gate",
                    description="North gate",
                    reachable_area_ids=[],
                ),
            }
        },
    )
    repo.create_campaign(campaign)
    return campaign_id, torch_stack.stack_id


def test_campaign_get_returns_selected_party_and_active_actor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id, torch_stack_id = _create_campaign(tmp_path)

    response = client.get("/api/v1/campaign/get", params={"campaign_id": campaign_id})
    assert response.status_code == 200
    body = response.json()
    assert body["campaign_id"] == campaign_id
    assert body["selected"]["party_character_ids"] == ["pc_001", "pc_002"]
    assert body["selected"]["active_actor_id"] == "pc_002"
    assert body["actors"] == {
        "pc_001": {
            "position": "area_001",
            "hp": 10,
            "character_state": "alive",
            "inventory": {"torch": 1},
        },
        "pc_002": {
            "position": "area_002",
            "hp": 10,
            "character_state": "alive",
            "inventory": {},
        },
    }
    assert body["inventory_stack_ids"] == {
        "pc_001": {"torch": [torch_stack_id]},
        "pc_002": {},
    }
    assert body["map"] == {
        "areas": {
            "area_001": {
                "id": "area_001",
                "name": "Camp",
                "description": "Initial camp",
                "parent_area_id": None,
                "reachable_area_ids": ["area_002"],
            },
            "area_002": {
                "id": "area_002",
                "name": "Gate",
                "description": "North gate",
                "parent_area_id": None,
                "reachable_area_ids": [],
            },
        }
    }
    assert body["status"] == {
        "ended": False,
        "reason": None,
        "ended_at": None,
        "milestone": {
            "current": "intro",
            "last_advanced_turn": 0,
            "turn_trigger_interval": 6,
            "pressure": 0,
            "pressure_threshold": 2,
            "summary": "",
        },
    }


def test_campaign_get_returns_404_for_missing_campaign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/v1/campaign/get", params={"campaign_id": "camp_missing"})
    assert response.status_code == 404
