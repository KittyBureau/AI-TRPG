from __future__ import annotations

import json
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


class _DummyLLMClient:
    def __init__(self, *args, **kwargs) -> None:
        pass


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("backend.app.turn_service.LLMClient", _DummyLLMClient)
    monkeypatch.chdir(tmp_path)
    app = create_app()
    return TestClient(app)


def _create_campaign(tmp_path: Path, campaign_id: str = "camp_get_001") -> tuple[str, str]:
    repo = FileRepo(tmp_path / "storage")
    torch_stack = create_runtime_item_stack(
        definition_id="torch",
        quantity=1,
        parent_type="actor",
        parent_id="pc_001",
        label="torch",
        stack_id_salt="test_campaign_get_endpoint:pc_001:torch",
    )
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
                inventory={},
                meta={},
            )
        },
        items={torch_stack.stack_id: torch_stack},
        map={
            "areas": {
                "area_001": MapArea(
                    id="area_001",
                    name="Camp",
                    description="Initial camp",
                    reachable_area_ids=[],
                )
            }
        },
    )
    repo.create_campaign(campaign)
    return campaign_id, torch_stack.stack_id


def test_campaign_get_reflects_party_load_and_select_actor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id, torch_stack_id = _create_campaign(tmp_path)

    create_character_resp = client.post(
        "/api/v1/characters/library",
        json={"id": "ch_smoke_001", "name": "Smoke Hero", "summary": "test profile"},
    )
    assert create_character_resp.status_code == 200

    load_resp = client.post(
        f"/api/v1/campaigns/{campaign_id}/party/load",
        json={"character_id": "ch_smoke_001"},
    )
    assert load_resp.status_code == 200
    assert "ch_smoke_001" in load_resp.json()["party_character_ids"]

    select_resp = client.post(
        "/api/v1/campaign/select_actor",
        json={"campaign_id": campaign_id, "active_actor_id": "ch_smoke_001"},
    )
    assert select_resp.status_code == 200
    assert select_resp.json()["active_actor_id"] == "ch_smoke_001"

    get_resp = client.get("/api/v1/campaign/get", params={"campaign_id": campaign_id})
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["campaign_id"] == campaign_id
    assert "ch_smoke_001" in body["selected"]["party_character_ids"]
    assert body["selected"]["active_actor_id"] == "ch_smoke_001"
    assert "ch_smoke_001" in body["actors"]
    assert "position" in body["actors"]["ch_smoke_001"]
    assert body["actors"]["pc_001"]["inventory"] == {"torch": 1}
    assert body["actors"]["ch_smoke_001"]["inventory"] == {}
    assert body["inventory_stack_ids"]["pc_001"] == {"torch": [torch_stack_id]}
    assert body["inventory_stack_ids"]["ch_smoke_001"] == {}
    assert body["map"]["areas"]["area_001"]["name"] == "Camp"


def test_campaign_get_keeps_party_list_stable_after_repeated_party_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id, _ = _create_campaign(tmp_path, campaign_id="camp_get_repeat")

    create_character_resp = client.post(
        "/api/v1/characters/library",
        json={"id": "ch_repeat_get", "name": "Repeat Get Hero"},
    )
    assert create_character_resp.status_code == 200

    first_load = client.post(
        f"/api/v1/campaigns/{campaign_id}/party/load",
        json={"character_id": "ch_repeat_get"},
    )
    second_load = client.post(
        f"/api/v1/campaigns/{campaign_id}/party/load",
        json={"character_id": "ch_repeat_get"},
    )
    assert first_load.status_code == 200
    assert second_load.status_code == 200

    get_resp = client.get("/api/v1/campaign/get", params={"campaign_id": campaign_id})
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["selected"]["party_character_ids"].count("ch_repeat_get") == 1
    assert list(body["actors"].keys()).count("ch_repeat_get") == 1


def test_campaign_get_returns_404_for_missing_campaign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/v1/campaign/get", params={"campaign_id": "camp_missing"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Campaign not found: camp_missing"


def test_campaign_get_returns_stable_500_for_invalid_campaign_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_dir = tmp_path / "storage" / "campaigns" / "camp_invalid"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    (campaign_dir / "campaign.json").write_text(
        json.dumps(
            {
                "id": "camp_invalid",
                "selected": {
                    "world_id": "world_001",
                    "party_character_ids": ["pc_001"],
                },
                "settings_snapshot": {},
                "goal": {"text": "Goal", "status": "active"},
                "milestone": {"current": "intro", "last_advanced_turn": 0},
            }
        ),
        encoding="utf-8",
    )

    response = client.get("/api/v1/campaign/get", params={"campaign_id": "camp_invalid"})
    assert response.status_code == 500
    assert response.json()["detail"] == "Campaign invalid: camp_invalid"
